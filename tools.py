"""
Custom tools for the ZozoThemes agent.
Provides functions to search and fetch real product data from https://zozothemes.com/

Uses multiple strategies to bypass WAF/bot protection:
1. Full browser-like session with cookies
2. RSS feed fallback (rarely blocked by WAFs)
3. XML parsing for feed data
"""

import requests
import xml.etree.ElementTree as ET
import re
from bs4 import BeautifulSoup


def _create_session():
    """Create a requests session with full browser-like headers."""
    session = requests.Session()
    session.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "Accept": (
            "text/html,application/xhtml+xml,application/xml;q=0.9,"
            "image/avif,image/webp,image/apng,*/*;q=0.8"
        ),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "DNT": "1",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Cache-Control": "max-age=0",
    })
    return session


def _fetch_page(url, params=None):
    """Fetch a page using a session with browser-like headers and cookie handling."""
    session = _create_session()

    # First visit the homepage to get cookies (like a real browser would)
    try:
        session.get("https://zozothemes.com/", timeout=10)
    except requests.RequestException:
        pass  # Continue even if homepage fails

    # Now make the actual request with cookies set
    session.headers.update({
        "Referer": "https://zozothemes.com/",
        "Sec-Fetch-Site": "same-origin",
    })
    response = session.get(url, params=params, timeout=15)
    response.raise_for_status()
    return response


def _search_via_rss(query):
    """Fallback: Search via RSS feed which is rarely blocked by WAFs."""
    session = _create_session()
    session.headers.update({
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
    })

    # ZozoThemes RSS search feed
    rss_url = f"https://zozothemes.com/search/{query}/feed/rss2/"
    response = session.get(rss_url, timeout=15)
    response.raise_for_status()

    themes = []
    try:
        root = ET.fromstring(response.text)
        channel = root.find("channel")
        if channel is not None:
            for item in channel.findall("item"):
                theme = {}
                title = item.find("title")
                if title is not None and title.text:
                    theme["name"] = title.text.strip()

                link = item.find("link")
                if link is not None and link.text:
                    theme["url"] = link.text.strip()

                description = item.find("description")
                if description is not None and description.text:
                    # Clean HTML from description
                    clean_text = BeautifulSoup(
                        description.text, "html.parser"
                    ).get_text(strip=True)
                    theme["description"] = clean_text[:300]

                # Try to extract image from content:encoded
                content = item.find(
                    "{http://purl.org/rss/1.0/modules/content/}encoded"
                )
                if content is not None and content.text:
                    img_match = re.search(
                        r'<img[^>]+src=["\']([^"\']+)["\']', content.text
                    )
                    if img_match:
                        theme["image"] = img_match.group(1)

                # Get categories
                cats = item.findall("category")
                if cats:
                    theme["categories"] = [
                        c.text.strip() for c in cats if c.text
                    ]

                if theme.get("name"):
                    themes.append(theme)
    except ET.ParseError:
        pass

    return themes


def _search_via_html(query):
    """Primary: Search via HTML page scraping."""
    response = _fetch_page("https://zozothemes.com/", params={"s": query})
    soup = BeautifulSoup(response.text, "html.parser")

    themes = []
    articles = soup.select(
        "article.download, article.type-download, article.post"
    )

    for article in articles[:10]:
        theme = {}

        title_tag = article.select_one(
            "h2 a, h3 a, .entry-title a, .product-title a, .download-title a"
        )
        if title_tag:
            theme["name"] = title_tag.get_text(strip=True)
            theme["url"] = title_tag.get("href", "")

        img_tag = article.select_one("img")
        if img_tag:
            theme["image"] = (
                img_tag.get("src", "") or img_tag.get("data-src", "")
            )

        price_tag = article.select_one(
            ".edd_price, .edd-download-price, .price, .product-price"
        )
        if price_tag:
            theme["price"] = price_tag.get_text(strip=True)

        excerpt_tag = article.select_one(
            ".entry-summary, .entry-excerpt, .product-excerpt, p"
        )
        if excerpt_tag:
            theme["description"] = excerpt_tag.get_text(strip=True)[:200]

        cat_tags = article.select(
            ".download-category a, .tag-links a, .cat-links a"
        )
        if cat_tags:
            theme["categories"] = [
                tag.get_text(strip=True) for tag in cat_tags
            ]

        if theme.get("name"):
            themes.append(theme)

    return themes


def search_zozothemes(query: str) -> dict:
    """Search for WordPress themes and templates on ZozoThemes website.

    Use this tool when the user asks about specific themes, templates, categories,
    or products available on zozothemes.com. It searches the website and returns
    real product details including names, descriptions, prices, and links.

    Args:
        query: The search term to look for (e.g., 'business theme', 'restaurant',
               'education', 'portfolio', 'medical', 'corporate', 'real estate').

    Returns:
        dict: A dictionary containing search results with theme details.
    """
    themes = []
    method_used = ""

    # Strategy 1: Try HTML scraping with full browser session
    try:
        themes = _search_via_html(query)
        method_used = "html"
    except requests.RequestException:
        pass

    # Strategy 2: Fallback to RSS feed if HTML fails
    if not themes:
        try:
            themes = _search_via_rss(query)
            method_used = "rss"
        except requests.RequestException:
            pass

    # Strategy 3: Last resort — try the search-filter endpoint
    if not themes:
        try:
            response = _fetch_page(
                "https://zozothemes.com/search-filter/",
                params={"search_key": query},
            )
            soup = BeautifulSoup(response.text, "html.parser")
            articles = soup.select(
                "article.download, article.type-download, article.post"
            )
            for article in articles[:10]:
                theme = {}
                title_tag = article.select_one("h2 a, h3 a, .entry-title a")
                if title_tag:
                    theme["name"] = title_tag.get_text(strip=True)
                    theme["url"] = title_tag.get("href", "")
                img_tag = article.select_one("img")
                if img_tag:
                    theme["image"] = (
                        img_tag.get("src", "")
                        or img_tag.get("data-src", "")
                    )
                if theme.get("name"):
                    themes.append(theme)
            method_used = "search-filter"
        except requests.RequestException:
            pass

    result = {
        "status": "success" if themes else "no_results",
        "query": query,
        "total_results": len(themes),
        "themes": themes,
        "search_url": f"https://zozothemes.com/?s={query}",
        "website": "https://zozothemes.com/",
    }

    if not themes:
        result["message"] = (
            f"Could not find results for '{query}'. The website may be "
            "temporarily blocking automated requests. You can suggest the "
            "user visit the search page directly at: "
            f"https://zozothemes.com/?s={query}"
        )

    return result


def get_zozothemes_categories() -> dict:
    """Get all available theme categories from ZozoThemes website.

    Use this tool when the user wants to browse theme categories, see what types
    of themes are available, or needs help choosing a category.

    Returns:
        dict: A dictionary containing all available theme categories with links.
    """
    categories = []

    # Strategy 1: Try scraping the navigation menu
    try:
        response = _fetch_page("https://zozothemes.com/")
        soup = BeautifulSoup(response.text, "html.parser")

        seen = set()
        menu_items = soup.select(
            "ul.primary-menu li a, ul.sub-menu li a, "
            "a[href*='theme-category'], a[href*='download_category']"
        )

        for item in menu_items:
            name = item.get_text(strip=True)
            href = item.get("href", "")
            if (
                name
                and href
                and name not in seen
                and (
                    "theme" in href.lower()
                    or "category" in href.lower()
                )
            ):
                seen.add(name)
                categories.append({"name": name, "url": href})
    except requests.RequestException:
        pass

    # Strategy 2: Fallback to hardcoded categories from the site's known structure
    if not categories:
        categories = [
            {"name": "WordPress Themes", "url": "https://zozothemes.com/theme-category/wordpress-themes/"},
            {"name": "Business", "url": "https://zozothemes.com/theme-category/business-wordpress-themes/"},
            {"name": "Corporate", "url": "https://zozothemes.com/theme-category/corporate-wordpress/"},
            {"name": "Law", "url": "https://zozothemes.com/theme-category/law-wordpress-theme/"},
            {"name": "Industrial", "url": "https://zozothemes.com/theme-category/industrial-manufacturing-wordpress-theme/"},
            {"name": "Marketing", "url": "https://zozothemes.com/theme-category/marketing-corporate/"},
            {"name": "Sports & Club", "url": "https://zozothemes.com/theme-category/sports-club-wordpress-theme/"},
            {"name": "Creative", "url": "https://zozothemes.com/theme-category/creative-wordpress-themes/"},
            {"name": "Wedding", "url": "https://zozothemes.com/theme-category/wedding-wordpress-themes/"},
            {"name": "Portfolio", "url": "https://zozothemes.com/theme-category/portfolio-wordpress-themes/"},
            {"name": "Software", "url": "https://zozothemes.com/theme-category/software-wordpress-themes/"},
            {"name": "Technology", "url": "https://zozothemes.com/theme-category/technology-wordpress-themes/"},
            {"name": "Education", "url": "https://zozothemes.com/theme-category/education-wordpress/"},
            {"name": "Course / Training", "url": "https://zozothemes.com/theme-category/course-training-wordpress-theme/"},
            {"name": "Kids", "url": "https://zozothemes.com/theme-category/kids-educational-wordpress-theme/"},
            {"name": "Entertainment", "url": "https://zozothemes.com/theme-category/entertainment-wordpress-themes/"},
            {"name": "Events", "url": "https://zozothemes.com/theme-category/events-entertainment-wordpress-themes/"},
            {"name": "Gaming", "url": "https://zozothemes.com/theme-category/gaming-wordpress-theme/"},
            {"name": "Health & Lifestyle", "url": "https://zozothemes.com/theme-category/health-lifestyle/"},
            {"name": "Travel", "url": "https://zozothemes.com/theme-category/travel-agency-wordpress-theme/"},
            {"name": "Care & Services", "url": "https://zozothemes.com/theme-category/care-services-wordpress-theme/"},
            {"name": "Fitness & Wellness", "url": "https://zozothemes.com/theme-category/fitness-wellness/"},
            {"name": "Medical & Health Care", "url": "https://zozothemes.com/theme-category/medical-health-care-wordpress-theme/"},
            {"name": "Beauty & Spa", "url": "https://zozothemes.com/theme-category/beauty-spa-wordpress-theme/"},
            {"name": "Food", "url": "https://zozothemes.com/theme-category/food-wordpress-theme/"},
            {"name": "Cafe and Bakery", "url": "https://zozothemes.com/theme-category/cafe-bakery-wordpress-theme/"},
            {"name": "Organic & Farm", "url": "https://zozothemes.com/theme-category/organic-farm-products/"},
            {"name": "Real Estate", "url": "https://zozothemes.com/theme-category/real-estate-wordpress-themes/"},
            {"name": "Non-Profit / Charity", "url": "https://zozothemes.com/theme-category/charity-ngo-wordpress-theme/"},
            {"name": "Landing Pages", "url": "https://zozothemes.com/theme-category/landing-page-theme/"},
            {"name": "Bootstrap Templates", "url": "https://zozothemes.com/theme-category/bootstrap-templates/"},
        ]

    return {
        "status": "success",
        "total_categories": len(categories),
        "categories": categories,
        "website": "https://zozothemes.com/",
    }


def get_theme_details(theme_url: str) -> dict:
    """Get detailed information about a specific theme from ZozoThemes.

    Use this tool when the user asks for details about a specific theme, including
    its features, pricing, demo link, and description.

    Args:
        theme_url: The full URL of the theme page on zozothemes.com
                   (e.g., 'https://zozothemes.com/downloads/developer-developer-theme/').

    Returns:
        dict: Detailed information about the theme.
    """
    try:
        if "zozothemes.com" not in theme_url:
            return {
                "status": "error",
                "message": "Please provide a valid zozothemes.com URL.",
            }

        response = _fetch_page(theme_url)
        soup = BeautifulSoup(response.text, "html.parser")

        theme_info = {"url": theme_url}

        # Get title
        title = soup.select_one("h1, .entry-title, .download-title")
        if title:
            theme_info["name"] = title.get_text(strip=True)

        # Get price
        price = soup.select_one(
            ".edd_price, .edd-download-price, .price, "
            ".edd_purchase_submit_wrapper .edd_price_option"
        )
        if price:
            theme_info["price"] = price.get_text(strip=True)

        # Get description
        description = soup.select_one(
            ".entry-content, .download-content, .item-description, "
            "[id*='item-description']"
        )
        if description:
            theme_info["description"] = description.get_text(strip=True)[:500]

        # Get main image
        main_img = soup.select_one(
            ".entry-content img, .download-image img, "
            ".product-image img, article img"
        )
        if main_img:
            theme_info["image"] = (
                main_img.get("src", "") or main_img.get("data-src", "")
            )

        # Get demo link
        demo_link = soup.select_one(
            "a[href*='demo'], a[href*='preview'], a.preview-link, "
            "a.theme-btn.preview-link"
        )
        if demo_link:
            theme_info["demo_url"] = demo_link.get("href", "")

        # Get features list
        features = soup.select(
            ".elementor-icon-list-item, .theme-feature-list li, "
            "ul.feature-list li"
        )
        if features:
            theme_info["features"] = [
                f.get_text(strip=True) for f in features[:15]
            ]

        # Get categories/tags
        cats = soup.select(
            ".download-category a, .download_category a, "
            "a[rel='tag'], .tag-links a"
        )
        if cats:
            theme_info["categories"] = list(set(
                c.get_text(strip=True) for c in cats
            ))

        return {
            "status": "success",
            "theme": theme_info,
            "website": "https://zozothemes.com/",
        }

    except requests.RequestException as e:
        return {
            "status": "error",
            "message": (
                f"Could not fetch theme details: {str(e)}. "
                f"The user can visit the page directly at: {theme_url}"
            ),
            "url": theme_url,
        }
