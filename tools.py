"""
Custom tools for the ZozoThemes agent.
Provides functions to search and fetch real product data from https://zozothemes.com/
"""

import requests
from bs4 import BeautifulSoup


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
    try:
        # Use the ZozoThemes search filter endpoint
        url = "https://zozothemes.com/"
        params = {"s": query}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(url, params=params, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        themes = []

        # Parse product/download items from search results
        articles = soup.select("article.download, article.type-download, article.post")

        for article in articles[:10]:  # Limit to top 10 results
            theme = {}

            # Get theme title
            title_tag = article.select_one(
                "h2 a, h3 a, .entry-title a, .product-title a, .download-title a"
            )
            if title_tag:
                theme["name"] = title_tag.get_text(strip=True)
                theme["url"] = title_tag.get("href", "")

            # Get theme image
            img_tag = article.select_one("img")
            if img_tag:
                theme["image"] = img_tag.get("src", "") or img_tag.get("data-src", "")

            # Get price
            price_tag = article.select_one(
                ".edd_price, .edd-download-price, .price, .product-price"
            )
            if price_tag:
                theme["price"] = price_tag.get_text(strip=True)

            # Get description/excerpt
            excerpt_tag = article.select_one(
                ".entry-summary, .entry-excerpt, .product-excerpt, p"
            )
            if excerpt_tag:
                theme["description"] = excerpt_tag.get_text(strip=True)[:200]

            # Get category tags
            cat_tags = article.select(".download-category a, .tag-links a, .cat-links a")
            if cat_tags:
                theme["categories"] = [tag.get_text(strip=True) for tag in cat_tags]

            # Only add if we have at least a name
            if theme.get("name"):
                themes.append(theme)

        if not themes:
            # Fallback: try to find any product-like links on the page
            product_links = soup.select("a[href*='/downloads/'], a[href*='theme']")
            seen_names = set()
            for link in product_links[:10]:
                name = link.get_text(strip=True)
                href = link.get("href", "")
                if name and len(name) > 3 and name not in seen_names and "zozothemes.com" in href:
                    seen_names.add(name)
                    themes.append({"name": name, "url": href})

        result = {
            "status": "success",
            "query": query,
            "total_results": len(themes),
            "themes": themes,
            "search_url": f"https://zozothemes.com/?s={query}",
            "website": "https://zozothemes.com/",
        }

        if not themes:
            result["message"] = (
                f"No exact matches found for '{query}'. "
                "Try broader terms like 'business', 'corporate', 'education', "
                "'medical', 'food', 'portfolio', 'creative', or 'landing page'."
            )

        return result

    except requests.RequestException as e:
        return {
            "status": "error",
            "message": f"Could not fetch data from zozothemes.com: {str(e)}",
            "website": "https://zozothemes.com/",
        }


def get_zozothemes_categories() -> dict:
    """Get all available theme categories from ZozoThemes website.

    Use this tool when the user wants to browse theme categories, see what types
    of themes are available, or needs help choosing a category.

    Returns:
        dict: A dictionary containing all available theme categories with links.
    """
    try:
        url = "https://zozothemes.com/"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        categories = []
        seen = set()

        # Parse navigation menu for categories
        menu_items = soup.select(
            "ul.primary-menu li a, ul.sub-menu li a, "
            "a[href*='theme-category'], a[href*='download_category']"
        )

        for item in menu_items:
            name = item.get_text(strip=True)
            href = item.get("href", "")
            if name and href and name not in seen and ("theme" in href.lower() or "category" in href.lower()):
                seen.add(name)
                categories.append({
                    "name": name,
                    "url": href,
                })

        return {
            "status": "success",
            "total_categories": len(categories),
            "categories": categories,
            "website": "https://zozothemes.com/",
        }

    except requests.RequestException as e:
        return {
            "status": "error",
            "message": f"Could not fetch categories from zozothemes.com: {str(e)}",
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

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }

        response = requests.get(theme_url, headers=headers, timeout=15)
        response.raise_for_status()

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
            # Get first 500 chars of clean text
            theme_info["description"] = description.get_text(strip=True)[:500]

        # Get main image
        main_img = soup.select_one(
            ".entry-content img, .download-image img, "
            ".product-image img, article img"
        )
        if main_img:
            theme_info["image"] = main_img.get("src", "") or main_img.get("data-src", "")

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
            "message": f"Could not fetch theme details: {str(e)}",
            "url": theme_url,
        }
