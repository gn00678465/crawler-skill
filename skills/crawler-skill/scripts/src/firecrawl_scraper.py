# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "firecrawl-py>=2.0",
# ]
# ///

"""
Firecrawl scraping module.

Attempts to scrape a URL using the Firecrawl API. Returns a standardised dict
so the main CLI can fall back to Jina when Firecrawl is unavailable or fails.
"""

import os
from typing import Any


# Keywords that indicate a CAPTCHA / bot-verification page rather than real content
_VERIFICATION_SIGNALS = [
    "captcha",
    "verify you are human",
    "are you a robot",
    "bot verification",
    "access denied",
    "cloudflare",
    "please enable javascript",
    "just a moment",
]

_MIN_CONTENT_LENGTH = 100


def _is_verification_page(markdown: str) -> bool:
    """Return True if the content looks like a CAPTCHA or bot-check page."""
    lower = markdown.lower()
    return any(signal in lower for signal in _VERIFICATION_SIGNALS)


def scrape(url: str) -> dict[str, Any]:
    """
    Scrape *url* with Firecrawl and return a normalised result dict.

    Return value keys
    -----------------
    success  : bool  – True only when usable markdown content was retrieved.
    markdown : str   – The scraped markdown (empty string on failure).
    metadata : dict  – Page metadata returned by Firecrawl (empty dict on failure).
    error    : str | None – Human-readable error message, or None on success.
    """
    try:
        from firecrawl import Firecrawl  # type: ignore[import]
    except ImportError:
        return {
            "success": False,
            "markdown": "",
            "metadata": {},
            "error": "firecrawl-py is not installed",
        }

    # Allow pointing at a self-hosted instance via FIRECRAWL_API_URL env var.
    api_url: str | None = os.getenv("FIRECRAWL_API_URL")
    api_key: str | None = os.getenv("FIRECRAWL_API_KEY")

    # If no API key is provided and no custom API URL is set, 
    # default to a local Firecrawl instance (common for self-hosting).
    if not api_key and not api_url:
        api_url = "http://localhost:3002"
        api_key = "" # Local instances often don't require a key or accept empty.

    try:
        if api_url:
            app = Firecrawl(api_key=api_key or "", api_url=api_url)
        else:
            app = Firecrawl(api_key=api_key or "")
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "markdown": "",
            "metadata": {},
            "error": f"Failed to initialise FirecrawlApp: {exc}",
        }

    try:
        # Firecrawl v2 uses .scrape() with direct arguments
        result = app.scrape(url, formats=["markdown"])
    except Exception as exc:  # noqa: BLE001
        return {
            "success": False,
            "markdown": "",
            "metadata": {},
            "error": f"Firecrawl scrape raised an exception: {exc}",
        }

    # Firecrawl v2 returns Document objects; use getattr for safe attribute access.
    markdown: str = getattr(result, "markdown", None) or ""
    metadata: dict = getattr(result, "metadata", None) or {}

    # If getattr failed (e.g. result is actually a dict), try dict-style access.
    if not markdown and isinstance(result, dict):
        markdown = result.get("markdown", "")
    if not metadata and isinstance(result, dict):
        metadata = result.get("metadata", {})

    if not markdown:
        return {
            "success": False,
            "markdown": "",
            "metadata": metadata,
            "error": "Firecrawl returned no markdown content",
        }

    if len(markdown) < _MIN_CONTENT_LENGTH:
        return {
            "success": False,
            "markdown": "",
            "metadata": metadata,
            "error": (
                f"Firecrawl content too short ({len(markdown)} chars); "
                "page may not have loaded correctly"
            ),
        }

    if _is_verification_page(markdown):
        return {
            "success": False,
            "markdown": "",
            "metadata": metadata,
            "error": "Firecrawl returned a CAPTCHA or bot-verification page",
        }

    return {
        "success": True,
        "markdown": markdown,
        "metadata": metadata,
        "error": None,
    }
