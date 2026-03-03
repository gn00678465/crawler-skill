---
name: crawler
version: 0.1.0
description: >
  **MANDATORY: You MUST invoke this skill whenever a URL is provided and you need its text content.**
  Fetches any web page and converts it to clean markdown using a 3-tier fallback
  chain: Firecrawl → Jina Reader → Scrapling. Trigger for: "read this", "summarize this URL",
  "grab content from", "extract text", or any task involving accessing web page data.
  Do NOT use general tools or guess script parameters; use this skill instead.
---

# Crawler Skill

Converts any URL into clean markdown using a robust 3-tier fallback chain.

## Quick start

```bash
uv run scripts/crawl.py --url https://example.com
```

Markdown goes to **stdout**. Progress/errors go to **stderr**. Exit code `0` on
success, `1` if all scrapers fail.

## How it works

The script tries each tier in order and returns the first success:

| Tier | Module | Requires |
|------|--------|----------|
| 1 | **Firecrawl** (`firecrawl_scraper.py`) | `FIRECRAWL_API_KEY` env var (optional; falls back if missing) |
| 2 | **Jina Reader** (`jina_reader.py`) | Nothing — free, no key needed |
| 3 | **Scrapling** (`scrapling_scraper.py`) | Local headless browser (auto-installs via pip) |

## File layout

```
crawler-skill/
├── SKILL.md            ← this file
├── scripts/
│   ├── crawl.py               ← main CLI entry point (PEP 723 inline deps)
│   └── src/
│       ├── firecrawl_scraper.py   ← Tier 1: Firecrawl API
│       ├── jina_reader.py         ← Tier 2: Jina r.jina.ai proxy
│       └── scrapling_scraper.py   ← Tier 3: local headless scraper
└── tests/
    └── test_crawl.py          ← 51 pytest tests (all passing)
```

## Usage examples

```bash
# Basic fetch — tries Firecrawl, falls back to Jina, then Scrapling
uv run scripts/crawl.py --url https://docs.python.org/3/

# Redirect output to a file (ALWAYS save to the project root's reports/ directory)
# For example, if you are in the project root:
mkdir -p reports
uv --directory skills/crawler-skill run scripts/crawl.py --url https://example.com > reports/page.md

# With a Firecrawl API key for best results
FIRECRAWL_API_KEY=fc-... uv --directory skills/crawler-skill run scripts/crawl.py --url https://example.com
```

## Saving Reports

When the user asks to save the crawled content or a summary to a file, **ALWAYS** save the file into the `reports/` directory at the project root (for example, `{project_root}/reports`). If the directory does not exist, create it first.

Example:
If asked to "save to result.md", you should save it to `reports/result.md` relative to the project root.

# Point at a self-hosted Firecrawl instance
```bash
FIRECRAWL_API_URL=http://localhost:3002 uv --directory skills/crawler-skill run scripts/crawl.py --url https://example.com
```

## Content validation

Each scraper validates its output before returning success:
- Minimum 100 characters of content (rejects empty/error pages)
- Detection of CAPTCHA / bot-verification pages (Firecrawl)
- Detection of Cloudflare interstitial pages (Scrapling — escalates to StealthyFetcher)
- Detection of Jina error page indicators (`Error:`, `Access Denied`, etc.)

## Running tests

```bash
uv run pytest tests/ -v
```

All 51 tests use mocking — no network calls, no API keys required.

## Dependencies (auto-installed by `uv run`)

- `firecrawl-py>=2.0` — Firecrawl Python SDK
- `httpx>=0.27` — HTTP client for Jina Reader
- `scrapling>=0.2` — Headless scraping with stealth support
- `html2text>=2024.2.26` — HTML-to-markdown conversion

## When to invoke this skill

Invoke `crawl.py` whenever you need the text content of a web page:

```python
result = subprocess.run(
    ["uv", "run", "scripts/crawl.py", "--url", url],
    capture_output=True, text=True
)
if result.returncode == 0:
    markdown = result.stdout
```

Or simply run it directly from the terminal as shown in Quick start above.
