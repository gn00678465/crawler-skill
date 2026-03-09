#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "firecrawl-py>=2.0",
#     "httpx>=0.27",
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
from urllib.parse import urlparse

# Add the src directory to the module search path so we can import our modules.
_SRC_DIR = Path(__file__).parent / "src"
sys.path.insert(0, str(_SRC_DIR))

import firecrawl_scraper  # noqa: E402
import jina_reader        # noqa: E402
import scrapling_scraper  # noqa: E402
import domain_router      # noqa: E402

def _log(message: str) -> None:
    """Write a status message to stderr."""
    print(message, file=sys.stderr)


def crawl(url: str) -> tuple[bool, str]:
    """
    Try each scraper tier in turn, returning the first successful result.

    The active tiers are selected by ``domain_router.get_tiers()`` so that
    certain domains can bypass specific scrapers (e.g. medium.com skips
    Firecrawl; mp.weixin.qq.com uses Scrapling only).

    Returns
    -------
    (success, markdown) where success is True and markdown is non-empty
    on success, or (False, "") if all active scrapers failed.
    """
    tiers = domain_router.get_tiers(url)
    _log(f"[crawl] Tiers for {url}: {', '.join(tiers)}")

    # --- Tier 1: Firecrawl ---
    if "firecrawl" in tiers:
        _log(f"[crawl] Trying Firecrawl for: {url}")
        result = firecrawl_scraper.scrape(url)
        if result["success"]:
            _log("[crawl] Firecrawl succeeded.")
            return True, result["markdown"]
        _log(f"[crawl] Firecrawl failed: {result['error']}")

    # --- Tier 2: Jina Reader ---
    if "jina" in tiers:
        _log(f"[crawl] Trying Jina Reader for: {url}")
        result = jina_reader.fetch(url)
        if result["success"]:
            _log("[crawl] Jina Reader succeeded.")
            return True, result["markdown"]
        _log(f"[crawl] Jina Reader failed: {result['error']}")

    # --- Tier 3: Scrapling ---
    if "scrapling" in tiers:
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
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="Optional: Save the markdown output to this file path.",
    )
    args = parser.parse_args()

    url = args.url.strip()
    if not url:
        print("Error: --url must not be empty.", file=sys.stderr)
        return 1

    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        print(
            f"Error: invalid URL '{url}'. Only http:// and https:// URLs are supported.",
            file=sys.stderr,
        )
        return 1

    success, markdown = crawl(url)
    if success:
        if args.output:
            output_path = Path(args.output).resolve()
            try:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_text(markdown, encoding="utf-8")
                _log(f"[crawl] Successfully saved markdown to: {output_path}")
            except Exception as exc:
                print(f"Error saving to {output_path}: {exc}", file=sys.stderr)
                return 1
        else:
            # Write as UTF-8 bytes to avoid Windows terminal encoding errors (cp950, etc.)
            sys.stdout.buffer.write((markdown + "\n").encode("utf-8"))
        return 0
    else:
        print(f"Error: Failed to fetch '{url}' with all available scrapers.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
