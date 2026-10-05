"""Resolve a Gemini chat model that works with the current GOOGLE_API_KEY.

Tries candidates in order (or GEMINI_MODEL first if set). The first model
that successfully returns generateContent is used by all agents.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

# Free-tier chat models, newest first. Skip TTS, image, embed, and transcribe.
GEMINI_MODEL_CANDIDATES = [
    "gemini-3.8-flash",
    "gemini-3.7-flash",
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-3.5-flash-lite",
    "gemini-3.1-flash-lite",
    "gemini-flash-latest",
    "gemini-flash-lite-latest",
    "gemini-3-flash-preview",
]

_CACHE_FILE = Path(__file__).resolve().parent / ".adk" / "resolved_gemini_model.txt"
_resolved: str | None = None
_probe_log: list[str] = []


def _load_dotenv() -> None:
    env_path = Path(__file__).with_name(".env")
    if not env_path.is_file():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def _api_key() -> str:
    _load_dotenv()
    key = os.environ.get("GOOGLE_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GOOGLE_API_KEY is not set. Add it to .env and restart the agent."
        )
    return key


def _probe(model: str, key: str) -> bool:
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={urllib.parse.quote(key)}"
    )
    body = json.dumps(
        {"contents": [{"parts": [{"text": "Reply with the single word OK"}]}]}
    ).encode()
    req = urllib.request.Request(
        url, data=body, headers={"Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode())
        parts = (
            payload.get("candidates", [{}])[0]
            .get("content", {})
            .get("parts", [])
        )
        text = "".join(p.get("text", "") for p in parts)
        _probe_log.append(f"OK {model}")
        return bool(text.strip() or payload.get("candidates"))
    except urllib.error.HTTPError as exc:
        err = exc.read().decode(errors="replace")
        try:
            message = json.loads(err).get("error", {}).get("message", err)
        except json.JSONDecodeError:
            message = err
        _probe_log.append(f"FAIL {model} ({exc.code}): {str(message)[:160]}")
        return False
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        _probe_log.append(f"FAIL {model}: {exc}")
        return False


def _read_cache() -> str | None:
    try:
        cached = _CACHE_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return cached or None


def _write_cache(model: str) -> None:
    try:
        _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        _CACHE_FILE.write_text(model + "\n", encoding="utf-8")
    except OSError:
        pass


def resolve_gemini_model(force: bool = False) -> str:
    """Return the first Gemini model that accepts this API key."""
    global _resolved
    if _resolved and not force:
        return _resolved

    override = os.environ.get("GEMINI_MODEL", "").strip()
    candidates = list(GEMINI_MODEL_CANDIDATES)
    if override:
        candidates = [override] + [c for c in candidates if c != override]

    key = _api_key()
    _probe_log.clear()

    cached = None if force else _read_cache()
    if cached and cached in candidates:
        if _probe(cached, key):
            _resolved = cached
            print(f"[myDemoAgent] Using Gemini model: {_resolved} (cached)")
            return _resolved
        _probe_log.append(f"CACHE_STALE {cached}")

    for model in candidates:
        if _probe(model, key):
            _resolved = model
            _write_cache(model)
            print(f"[myDemoAgent] Using Gemini model: {_resolved}")
            for line in _probe_log:
                print(f"[myDemoAgent]   {line}")
            return _resolved

    details = "\n".join(f"  {line}" for line in _probe_log) or "  (no probes ran)"
    raise RuntimeError(
        "No working Gemini chat model for this API key. Tried:\n" + details
    )


GEMINI_MODEL = resolve_gemini_model()
