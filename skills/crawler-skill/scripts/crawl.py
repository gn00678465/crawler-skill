#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "firecrawl-py>=2.0",
#     "httpx>=0.27",
#     "scrapling>=0.2",
#     "html2text>=2024.2.26",
# ]
# ///

"""
crawl.py – Web page to markdown converter with 3-tier fallback chain.

Usage:
    uv run crawl.py --url https://example.com

Fallback order:
    1. Firecrawl (requires FIRECRAWL_API_KEY env var)
    2. Jina Reader (free, no key required)
    3. Scrapling   (local headless browser fallback)

Outputs clean markdown to stdout.
Status/progress messages go to stderr.
Exit code: 0 on success, 1 if all scrapers fail.
"""

import argparse
import sys
from pathlib import Path

# Add the src directory to the module search path so we can import our modules.
_SRC_DIR = Path(__file__).parent / "src"
sys.path.insert(0, str(_SRC_DIR))

import firecrawl_scraper  # noqa: E402
import jina_reader        # noqa: E402
import scrapling_scraper  # noqa: E402


def _log(message: str) -> None:
    """Write a status message to stderr."""
    print(message, file=sys.stderr)


def crawl(url: str) -> tuple[bool, str]:
    """
    Try each scraper in turn, returning the first successful result.

    Returns
    -------
    (success, markdown) where success is True and markdown is non-empty
    on success, or (False, "") if all scrapers failed.
    """
    # --- Tier 1: Firecrawl ---
    _log(f"[crawl] Trying Firecrawl for: {url}")
    result = firecrawl_scraper.scrape(url)
    if result["success"]:
        _log("[crawl] Firecrawl succeeded.")
        return True, result["markdown"]
    _log(f"[crawl] Firecrawl failed: {result['error']}")

    # --- Tier 2: Jina Reader ---
    _log(f"[crawl] Trying Jina Reader for: {url}")
    result = jina_reader.fetch(url)
    if result["success"]:
        _log("[crawl] Jina Reader succeeded.")
        return True, result["markdown"]
    _log(f"[crawl] Jina Reader failed: {result['error']}")

    # --- Tier 3: Scrapling ---
    _log(f"[crawl] Trying Scrapling for: {url}")
    result = scrapling_scraper.scrape(url)
    if result["success"]:
        _log("[crawl] Scrapling succeeded.")
        return True, result["markdown"]
    _log(f"[crawl] Scrapling failed: {result['error']}")

    _log("[crawl] All scrapers failed.")
    return False, ""


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch a web page and output clean markdown.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  uv run crawl.py --url https://example.com\n"
            "  uv run crawl.py --url https://docs.python.org/3/\n"
        ),
    )
    parser.add_argument(
        "--url",
        required=True,
        metavar="URL",
        help="The URL to fetch and convert to markdown.",
    )
    args = parser.parse_args()

    url = args.url.strip()
    if not url:
        print("Error: --url must not be empty.", file=sys.stderr)
        return 1

    success, markdown = crawl(url)
    if success:
        # Write as UTF-8 bytes to avoid Windows terminal encoding errors (cp950, etc.)
        sys.stdout.buffer.write((markdown + "\n").encode("utf-8"))
        return 0
    else:
        print(f"Error: Failed to fetch '{url}' with all available scrapers.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
