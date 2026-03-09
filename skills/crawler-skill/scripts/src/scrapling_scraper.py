# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "scrapling>=0.2",
#     "curl_cffi>=0.7.0",
#     "playwright>=1.41.0",
#     "patchright>=1.41.0",
#     "browserforge>=1.1.0",
#     "msgspec>=0.18.0",
#     "html2text>=2024.2.26",
# ]
# ///

"""
Scrapling fallback scraper module.

Tries a basic Fetcher.get() first; if a 403 or Cloudflare challenge is detected,
automatically falls back to StealthyFetcher for headless-browser-based retrieval.
Returns a normalised dict suitable for downstream markdown processing.
"""

from __future__ import annotations

import html2text

_CLOUDFLARE_MARKERS = (
    "cf-browser-verification",
    "cf_clearance",
    "challenge-running",
    "Just a moment",
    "Checking if the site connection is secure",
    "Enable JavaScript and cookies to continue",
    "/_cf_chl_opt",
    "cf-challenge",
)

_MIN_CONTENT_LENGTH = 100


def _is_cloudflare_page(html: str) -> bool:
    """Return True if the HTML looks like a Cloudflare interstitial/challenge page."""
    html_lower = html.lower()
    return any(marker.lower() in html_lower for marker in _CLOUDFLARE_MARKERS)


def _html_to_markdown(html: str) -> str:
    """Convert an HTML string to markdown using html2text."""
    converter = html2text.HTML2Text()
    converter.ignore_links = False
    converter.ignore_images = False
    converter.body_width = 0  # no line wrapping
    return converter.handle(html)


def scrape(url: str) -> dict:
    """Fetch *url* and return its content as markdown.

    Strategy:
    1. Try ``Fetcher.get()`` (lightweight, no browser).
    2. If the response is HTTP 403 **or** the body contains Cloudflare challenge
       markers, fall back to ``StealthyFetcher.fetch()`` with
       ``solve_cloudflare=True``.
    3. Convert the final HTML to markdown with html2text.
    4. Validate that the markdown is longer than ``_MIN_CONTENT_LENGTH`` chars.

    Returns
    -------
    dict with keys:
        success  (bool)  – True when usable markdown was produced.
        markdown (str)   – Converted markdown (empty string on failure).
        metadata (dict)  – url, status_code, fetcher_used, content_length.
        error    (str | None) – Human-readable error message, or None.
    """
    result: dict = {
        "success": False,
        "markdown": "",
        "metadata": {
            "url": url,
            "status_code": None,
            "fetcher_used": None,
            "content_length": 0,
        },
        "error": None,
    }

    page = None
    fetcher_used = "Fetcher"

    # Lazy import so the heavy scrapling/curl_cffi stack is only loaded when
    # Tier 3 is actually reached — Tier 1 and Tier 2 can run without it.
    try:
        from scrapling.fetchers import Fetcher, StealthyFetcher  # noqa: PLC0415
    except ImportError as exc:
        result["error"] = f"scrapling import failed: {exc}"
        return result

    # --- Step 1: basic fetch ---
    try:
        page = Fetcher.get(url, stealthy_headers=True, follow_redirects=True)
        result["metadata"]["status_code"] = page.status
    except Exception as exc:
        result["error"] = f"Fetcher error: {exc}"
        return result

    # --- Step 2: detect need for stealth ---
    body_html: str = page.body if isinstance(page.body, str) else page.body.decode("utf-8", errors="replace")
    needs_stealth = page.status == 403 or _is_cloudflare_page(body_html)

    if needs_stealth:
        fetcher_used = "StealthyFetcher"
        try:
            page = StealthyFetcher.fetch(
                url,
                headless=True,
                solve_cloudflare=True,
                block_webrtc=True,
                hide_canvas=True,
                network_idle=True,
                timeout=60000,
            )
            result["metadata"]["status_code"] = page.status
            body_html = page.body if isinstance(page.body, str) else page.body.decode("utf-8", errors="replace")
        except Exception as exc:
            result["error"] = f"StealthyFetcher error: {exc}"
            return result

    result["metadata"]["fetcher_used"] = fetcher_used

    # --- Step 3: convert HTML to markdown ---
    try:
        markdown = _html_to_markdown(body_html)
    except Exception as exc:
        result["error"] = f"HTML-to-markdown conversion error: {exc}"
        return result

    # --- Step 4: validate content length ---
    content_length = len(markdown.strip())
    result["metadata"]["content_length"] = content_length

    if content_length < _MIN_CONTENT_LENGTH:
        result["error"] = (
            f"Content too short after conversion ({content_length} chars); "
            "page may be empty or blocked."
        )
        return result

    result["success"] = True
    result["markdown"] = markdown
    return result


if __name__ == "__main__":
    import sys
    import json
    import argparse
    from pathlib import Path

    parser = argparse.ArgumentParser(description="Scrapling scraper module.")
    parser.add_argument("url", help="The URL to scrape.")
    parser.add_argument("--output", help="Optional path to save the markdown output.")
    
    args = parser.parse_args()
    output = scrape(args.url)
    
    if output["success"] and args.output:
        report_path = Path(args.output).resolve()
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with report_path.open("w", encoding="utf-8") as f:
            f.write(output["markdown"])
        print(f"Markdown saved to {report_path}", file=sys.stderr)
    
    # Always print JSON to stdout for programmatic use
    sys.stdout.buffer.write(json.dumps(output, indent=2, ensure_ascii=False).encode("utf-8"))
