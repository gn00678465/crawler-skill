# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "httpx>=0.27",
# ]
# ///

"""
Jina Reader module for crawler-skill.

Fetches web pages via the Jina Reader API (r.jina.ai), returning
clean markdown suitable for LLM processing. On any failure, returns
success=False so the main CLI can fall back to Scrapling.
"""

import httpx


JINA_BASE_URL = "https://r.jina.ai/"

HEADERS = {
    "Accept": "text/markdown",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
}

# Minimum content length to consider a response valid
MIN_CONTENT_LENGTH = 100

# Strings that indicate Jina returned an error page rather than real content
ERROR_INDICATORS = [
    "Error: ",
    "429 Too Many Requests",
    "503 Service Unavailable",
    "Access Denied",
    "Blocked",
]


def fetch(url: str, timeout: float = 60.0) -> dict:
    """
    Fetch a URL via the Jina Reader API and return its markdown content.

    Args:
        url: The target URL to fetch.
        timeout: HTTP request timeout in seconds.

    Returns:
        A dict with keys:
            success (bool): True if content was fetched and validated.
            markdown (str): The returned markdown content, or "" on failure.
            metadata (dict): Extracted metadata (url, content_length).
            error (str | None): Error message on failure, None on success.
    """
    jina_url = JINA_BASE_URL + url

    try:
        response = httpx.get(
            jina_url,
            headers=HEADERS,
            timeout=timeout,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.TimeoutException as exc:
        return _failure(url, f"Request timed out after {timeout}s: {exc}")
    except httpx.HTTPStatusError as exc:
        return _failure(
            url,
            f"HTTP {exc.response.status_code} from Jina Reader: {exc.response.text[:200]}",
        )
    except httpx.RequestError as exc:
        return _failure(url, f"Network error fetching via Jina Reader: {exc}")

    content = response.text

    # Validate content length
    if len(content) < MIN_CONTENT_LENGTH:
        return _failure(
            url,
            f"Jina Reader returned suspiciously short content ({len(content)} chars)",
        )

    # Check for error page indicators
    for indicator in ERROR_INDICATORS:
        if content.lstrip().startswith(indicator):
            return _failure(
                url,
                f"Jina Reader returned an error page (starts with '{indicator}')",
            )

    return {
        "success": True,
        "markdown": content,
        "metadata": {
            "url": url,
            "jina_url": jina_url,
            "content_length": len(content),
            "status_code": response.status_code,
        },
        "error": None,
    }


def _failure(url: str, error: str) -> dict:
    return {
        "success": False,
        "markdown": "",
        "metadata": {"url": url},
        "error": error,
    }
