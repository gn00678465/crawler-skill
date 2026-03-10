"""
Tests for the crawler-skill CLI tool and its three scraping modules.

Run with:
    uv run pytest tests/ -v
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock
import pytest

# Make sure src/ and crawl.py are importable (both now live under scripts/)
_ROOT = Path(__file__).parent.parent
_SCRIPTS = _ROOT / "scripts"
_SRC = _SCRIPTS / "src"
sys.path.insert(0, str(_SRC))
sys.path.insert(0, str(_SCRIPTS))

# --- Stub out scrapling and curl_cffi before importing scrapling_scraper ---
# scrapling requires curl_cffi which may not be available in the test environment.
_mock_fetcher = MagicMock()
_mock_stealthy = MagicMock()
_scrapling_fetchers_stub = MagicMock()
_scrapling_fetchers_stub.Fetcher = _mock_fetcher
_scrapling_fetchers_stub.StealthyFetcher = _mock_stealthy

sys.modules.setdefault("curl_cffi", MagicMock())
sys.modules.setdefault("curl_cffi.curl", MagicMock())
sys.modules.setdefault("scrapling", MagicMock())
sys.modules.setdefault("scrapling.fetchers", _scrapling_fetchers_stub)

import firecrawl_scraper
import jina_reader
import scrapling_scraper
import crawl
import domain_router


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _long_str(length: int = 200) -> str:
    return "x" * length


def _short_str(length: int = 50) -> str:
    return "x" * length


# ===========================================================================
# firecrawl_scraper tests
# ===========================================================================

class TestFirecrawlIsVerificationPage:
    def test_captcha_detected(self):
        assert firecrawl_scraper._is_verification_page("Please complete the captcha") is True

    def test_human_verification_detected(self):
        assert firecrawl_scraper._is_verification_page("Verify you are human") is True

    def test_robot_check_detected(self):
        assert firecrawl_scraper._is_verification_page("Are you a robot?") is True

    def test_cloudflare_detected(self):
        assert firecrawl_scraper._is_verification_page("Cloudflare protection") is True

    def test_just_a_moment_detected(self):
        assert firecrawl_scraper._is_verification_page("Just a moment...") is True

    def test_normal_content_not_flagged(self):
        assert firecrawl_scraper._is_verification_page("# Hello World\n\nThis is a test page.") is False

    def test_access_denied_detected(self):
        assert firecrawl_scraper._is_verification_page("Access Denied") is True


class TestFirecrawlScrape:
    def test_import_error_returns_failure(self):
        """If firecrawl-py is not installed, scrape() should return success=False."""
        with patch.dict("sys.modules", {"firecrawl": None}):
            # Force ImportError by patching the import inside the function
            with patch("builtins.__import__", side_effect=ImportError("no module")):
                result = firecrawl_scraper.scrape("https://example.com")
        assert result["success"] is False
        assert result["markdown"] == ""
        assert result["error"] is not None

    def test_firecrawl_app_init_failure(self):
        """Firecrawl constructor raising an exception → success=False."""
        mock_app_cls = MagicMock(side_effect=RuntimeError("bad key"))
        with patch.dict("sys.modules", {"firecrawl": MagicMock(Firecrawl=mock_app_cls)}):
            with patch("firecrawl_scraper.Firecrawl" if hasattr(firecrawl_scraper, "Firecrawl") else "firecrawl.Firecrawl", mock_app_cls, create=True):
                # Patch the import inside scrape
                fake_firecrawl = MagicMock()
                fake_firecrawl.Firecrawl = MagicMock(side_effect=RuntimeError("bad key"))
                with patch.dict("sys.modules", {"firecrawl": fake_firecrawl}):
                    result = firecrawl_scraper.scrape("https://example.com")
        assert result["success"] is False
        assert "Failed to initialise" in result["error"]

    def test_scrape_url_exception_returns_failure(self):
        """scrape() raising an exception → success=False."""
        mock_app = MagicMock()
        mock_app.scrape.side_effect = RuntimeError("API error")
        mock_firecrawl = MagicMock()
        mock_firecrawl.Firecrawl.return_value = mock_app
        with patch.dict("sys.modules", {"firecrawl": mock_firecrawl}):
            result = firecrawl_scraper.scrape("https://example.com")
        assert result["success"] is False
        assert "Firecrawl scrape raised an exception" in result["error"]

    def test_no_markdown_in_result_returns_failure(self):
        """If scrape returns a result with no markdown → success=False."""
        mock_result = MagicMock()
        mock_result.markdown = None
        mock_result.metadata = {}
        mock_app = MagicMock()
        mock_app.scrape.return_value = mock_result
        mock_firecrawl = MagicMock()
        mock_firecrawl.Firecrawl.return_value = mock_app
        with patch.dict("sys.modules", {"firecrawl": mock_firecrawl}):
            result = firecrawl_scraper.scrape("https://example.com")
        assert result["success"] is False
        assert "no markdown" in result["error"]

    def test_short_markdown_returns_failure(self):
        """Content shorter than MIN_CONTENT_LENGTH → success=False."""
        mock_result = MagicMock()
        mock_result.markdown = "short"
        mock_result.metadata = {}
        mock_app = MagicMock()
        mock_app.scrape.return_value = mock_result
        mock_firecrawl = MagicMock()
        mock_firecrawl.Firecrawl.return_value = mock_app
        with patch.dict("sys.modules", {"firecrawl": mock_firecrawl}):
            result = firecrawl_scraper.scrape("https://example.com")
        assert result["success"] is False
        assert "too short" in result["error"]

    def test_verification_page_returns_failure(self):
        """CAPTCHA/bot-check content → success=False."""
        mock_result = MagicMock()
        mock_result.markdown = "Please complete the captcha " + _long_str(200)
        mock_result.metadata = {}
        mock_app = MagicMock()
        mock_app.scrape.return_value = mock_result
        mock_firecrawl = MagicMock()
        mock_firecrawl.Firecrawl.return_value = mock_app
        with patch.dict("sys.modules", {"firecrawl": mock_firecrawl}):
            result = firecrawl_scraper.scrape("https://example.com")
        assert result["success"] is False
        assert "CAPTCHA" in result["error"]

    def test_valid_markdown_returns_success(self):
        """Normal long markdown → success=True."""
        good_markdown = "# Hello World\n\n" + _long_str(200)
        mock_result = MagicMock()
        mock_result.markdown = good_markdown
        mock_result.metadata = {"title": "Hello World"}
        mock_app = MagicMock()
        mock_app.scrape.return_value = mock_result
        mock_firecrawl = MagicMock()
        mock_firecrawl.Firecrawl.return_value = mock_app
        with patch.dict("sys.modules", {"firecrawl": mock_firecrawl}):
            result = firecrawl_scraper.scrape("https://example.com")
        assert result["success"] is True
        assert result["markdown"] == good_markdown
        assert result["error"] is None


# ===========================================================================
# jina_reader tests
# ===========================================================================

class TestJinaReaderFetch:
    def test_success(self):
        """A 200 response with sufficient content → success=True."""
        good_content = "# Page Title\n\n" + _long_str(200)
        mock_response = MagicMock()
        mock_response.text = good_content
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        with patch("jina_reader.httpx.get", return_value=mock_response):
            result = jina_reader.fetch("https://example.com")
        assert result["success"] is True
        assert result["markdown"] == good_content
        assert result["error"] is None
        assert result["metadata"]["url"] == "https://example.com"

    def test_timeout_returns_failure(self):
        """A timeout exception → success=False."""
        import httpx
        with patch("jina_reader.httpx.get", side_effect=httpx.TimeoutException("timed out")):
            result = jina_reader.fetch("https://example.com")
        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    def test_http_status_error_returns_failure(self):
        """An HTTP 429 error → success=False."""
        import httpx
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Too Many Requests"
        http_error = httpx.HTTPStatusError(
            "429", request=MagicMock(), response=mock_response
        )
        with patch("jina_reader.httpx.get", side_effect=http_error):
            result = jina_reader.fetch("https://example.com")
        assert result["success"] is False
        assert "429" in result["error"]

    def test_request_error_returns_failure(self):
        """A network error → success=False."""
        import httpx
        with patch("jina_reader.httpx.get", side_effect=httpx.RequestError("connection refused")):
            result = jina_reader.fetch("https://example.com")
        assert result["success"] is False
        assert "Network error" in result["error"]

    def test_short_content_returns_failure(self):
        """Content shorter than MIN_CONTENT_LENGTH → success=False."""
        mock_response = MagicMock()
        mock_response.text = "tiny"
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        with patch("jina_reader.httpx.get", return_value=mock_response):
            result = jina_reader.fetch("https://example.com")
        assert result["success"] is False
        assert "short" in result["error"].lower()

    def test_error_indicator_in_content_returns_failure(self):
        """Content starting with an error indicator → success=False."""
        bad_content = "Error: " + _long_str(200)
        mock_response = MagicMock()
        mock_response.text = bad_content
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        with patch("jina_reader.httpx.get", return_value=mock_response):
            result = jina_reader.fetch("https://example.com")
        assert result["success"] is False
        assert "error page" in result["error"].lower()

    def test_jina_url_construction(self):
        """The Jina URL should prepend r.jina.ai/ to the target."""
        good_content = "# Content\n\n" + _long_str(200)
        mock_response = MagicMock()
        mock_response.text = good_content
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        with patch("jina_reader.httpx.get", return_value=mock_response) as mock_get:
            jina_reader.fetch("https://example.com")
        called_url = mock_get.call_args[0][0]
        assert called_url == "https://r.jina.ai/https://example.com"

    def test_metadata_contains_jina_url(self):
        """Successful result should have jina_url in metadata."""
        good_content = "# Hello\n\n" + _long_str(200)
        mock_response = MagicMock()
        mock_response.text = good_content
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        with patch("jina_reader.httpx.get", return_value=mock_response):
            result = jina_reader.fetch("https://example.com")
        assert "jina_url" in result["metadata"]
        assert result["metadata"]["content_length"] == len(good_content)

    def test_failure_has_empty_markdown(self):
        """Failed result should always have empty markdown string."""
        import httpx
        with patch("jina_reader.httpx.get", side_effect=httpx.RequestError("err")):
            result = jina_reader.fetch("https://example.com")
        assert result["markdown"] == ""


# ===========================================================================
# scrapling_scraper tests
# ===========================================================================

class TestScraplingHelpers:
    def test_cloudflare_markers_detected(self):
        for marker in ["cf-browser-verification", "cf_clearance", "Just a moment"]:
            assert scrapling_scraper._is_cloudflare_page(marker) is True

    def test_normal_html_not_flagged(self):
        assert scrapling_scraper._is_cloudflare_page("<html><body><h1>Hello</h1></body></html>") is False

    def test_cloudflare_markers_case_insensitive(self):
        """Markers in uppercase or mixed case should still be detected."""
        assert scrapling_scraper._is_cloudflare_page("CF-BROWSER-VERIFICATION") is True
        assert scrapling_scraper._is_cloudflare_page("JUST A MOMENT") is True
        assert scrapling_scraper._is_cloudflare_page("Enable JavaScript And Cookies To Continue") is True

    def test_html_to_markdown_converts_h1(self):
        md = scrapling_scraper._html_to_markdown("<h1>Title</h1>")
        assert "Title" in md

    def test_html_to_markdown_converts_links(self):
        md = scrapling_scraper._html_to_markdown('<a href="https://example.com">Link</a>')
        assert "example.com" in md or "Link" in md


class TestScraplingScrapeFetcher:
    def _make_page(self, html: str, status: int = 200):
        page = MagicMock()
        page.status = status
        page.body = html
        return page

    def test_successful_basic_fetch(self):
        html = "<html><body><h1>Hello World</h1><p>" + ("text " * 30) + "</p></body></html>"
        mock_page = self._make_page(html)
        with patch("scrapling.fetchers.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            result = scrapling_scraper.scrape("https://example.com")
        assert result["success"] is True
        assert "Hello World" in result["markdown"]
        assert result["metadata"]["fetcher_used"] == "Fetcher"

    def test_fetcher_exception_returns_failure(self):
        with patch("scrapling.fetchers.Fetcher") as MockFetcher:
            MockFetcher.get.side_effect = RuntimeError("connection refused")
            result = scrapling_scraper.scrape("https://example.com")
        assert result["success"] is False
        assert "Fetcher error" in result["error"]

    def test_403_triggers_stealthy_fetcher(self):
        html_403 = "<html><body>Forbidden</body></html>"
        html_success = "<html><body><h1>Success</h1><p>" + ("word " * 30) + "</p></body></html>"
        mock_page_403 = self._make_page(html_403, status=403)
        mock_page_ok = self._make_page(html_success, status=200)
        with patch("scrapling.fetchers.Fetcher") as MockFetcher, \
             patch("scrapling.fetchers.StealthyFetcher") as MockStealth:
            MockFetcher.get.return_value = mock_page_403
            MockStealth.fetch.return_value = mock_page_ok
            result = scrapling_scraper.scrape("https://example.com")
        assert result["success"] is True
        assert result["metadata"]["fetcher_used"] == "StealthyFetcher"
        MockStealth.fetch.assert_called_once()

    def test_cloudflare_page_triggers_stealthy_fetcher(self):
        cf_html = "<html><body>Just a moment...</body></html>"
        success_html = "<html><body><h1>Real Content</h1><p>" + ("data " * 30) + "</p></body></html>"
        mock_cf_page = self._make_page(cf_html, status=200)
        mock_ok_page = self._make_page(success_html, status=200)
        with patch("scrapling.fetchers.Fetcher") as MockFetcher, \
             patch("scrapling.fetchers.StealthyFetcher") as MockStealth:
            MockFetcher.get.return_value = mock_cf_page
            MockStealth.fetch.return_value = mock_ok_page
            result = scrapling_scraper.scrape("https://example.com")
        assert result["success"] is True
        assert result["metadata"]["fetcher_used"] == "StealthyFetcher"

    def test_stealthy_fetcher_exception_returns_failure(self):
        cf_html = "<html><body>Just a moment...</body></html>"
        mock_cf_page = self._make_page(cf_html, status=200)
        with patch("scrapling.fetchers.Fetcher") as MockFetcher, \
             patch("scrapling.fetchers.StealthyFetcher") as MockStealth:
            MockFetcher.get.return_value = mock_cf_page
            MockStealth.fetch.side_effect = RuntimeError("browser crash")
            result = scrapling_scraper.scrape("https://example.com")
        assert result["success"] is False
        assert "StealthyFetcher error" in result["error"]

    def test_short_content_after_conversion_fails(self):
        html = "<html><body><p>Hi</p></body></html>"
        mock_page = self._make_page(html, status=200)
        with patch("scrapling.fetchers.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            result = scrapling_scraper.scrape("https://example.com")
        assert result["success"] is False
        assert "too short" in result["error"].lower()

    def test_bytes_body_decoded_properly(self):
        """page.body as bytes should be decoded to string."""
        html_bytes = b"<html><body><h1>Bytes Content</h1><p>" + (b"word " * 30) + b"</p></body></html>"
        mock_page = MagicMock()
        mock_page.status = 200
        mock_page.body = html_bytes
        with patch("scrapling.fetchers.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            result = scrapling_scraper.scrape("https://example.com")
        assert result["success"] is True
        assert "Bytes Content" in result["markdown"]

    def test_metadata_url_present(self):
        html = "<html><body><h1>Test</h1><p>" + ("x " * 60) + "</p></body></html>"
        mock_page = self._make_page(html, status=200)
        with patch("scrapling.fetchers.Fetcher") as MockFetcher:
            MockFetcher.get.return_value = mock_page
            result = scrapling_scraper.scrape("https://example.com")
        assert result["metadata"]["url"] == "https://example.com"


# ===========================================================================
# crawl.py fallback chain tests
# ===========================================================================

class TestCrawlFallbackChain:
    def _make_success(self, markdown: str = None) -> dict:
        return {
            "success": True,
            "markdown": markdown or ("# Good\n\n" + _long_str()),
            "metadata": {},
            "error": None,
        }

    def _make_failure(self, error: str = "failed") -> dict:
        return {"success": False, "markdown": "", "metadata": {}, "error": error}

    def test_firecrawl_succeeds_first(self):
        """When Firecrawl succeeds, Jina and Scrapling should not be called."""
        fc_result = self._make_success("# From Firecrawl\n\n" + _long_str())
        with patch("crawl.firecrawl_scraper.scrape", return_value=fc_result) as mock_fc, \
             patch("crawl.jina_reader.fetch") as mock_jina, \
             patch("crawl.scrapling_scraper.scrape") as mock_scraping:
            success, markdown = crawl.crawl("https://example.com")
        assert success is True
        assert "Firecrawl" in markdown
        mock_fc.assert_called_once_with("https://example.com")
        mock_jina.assert_not_called()
        mock_scraping.assert_not_called()

    def test_firecrawl_fails_jina_succeeds(self):
        """When Firecrawl fails, Jina is tried; on Jina success, Scrapling not called."""
        jina_result = self._make_success("# From Jina\n\n" + _long_str())
        with patch("crawl.firecrawl_scraper.scrape", return_value=self._make_failure("fc error")), \
             patch("crawl.jina_reader.fetch", return_value=jina_result) as mock_jina, \
             patch("crawl.scrapling_scraper.scrape") as mock_scraping:
            success, markdown = crawl.crawl("https://example.com")
        assert success is True
        assert "Jina" in markdown
        mock_jina.assert_called_once_with("https://example.com")
        mock_scraping.assert_not_called()

    def test_firecrawl_and_jina_fail_scrapling_succeeds(self):
        """When Firecrawl and Jina fail, Scrapling is the final fallback."""
        scrapling_result = self._make_success("# From Scrapling\n\n" + _long_str())
        with patch("crawl.firecrawl_scraper.scrape", return_value=self._make_failure()), \
             patch("crawl.jina_reader.fetch", return_value=self._make_failure()), \
             patch("crawl.scrapling_scraper.scrape", return_value=scrapling_result) as mock_scraping:
            success, markdown = crawl.crawl("https://example.com")
        assert success is True
        assert "Scrapling" in markdown
        mock_scraping.assert_called_once_with("https://example.com")

    def test_all_scrapers_fail_returns_false(self):
        """When all three scrapers fail, crawl returns (False, '')."""
        with patch("crawl.firecrawl_scraper.scrape", return_value=self._make_failure("fc")), \
             patch("crawl.jina_reader.fetch", return_value=self._make_failure("jina")), \
             patch("crawl.scrapling_scraper.scrape", return_value=self._make_failure("scrapling")):
            success, markdown = crawl.crawl("https://example.com")
        assert success is False
        assert markdown == ""

    def test_crawl_passes_url_to_each_scraper(self):
        """Each scraper should receive the exact URL passed to crawl()."""
        target = "https://docs.python.org/3/"
        with patch("crawl.firecrawl_scraper.scrape", return_value=self._make_failure()) as mock_fc, \
             patch("crawl.jina_reader.fetch", return_value=self._make_failure()) as mock_jina, \
             patch("crawl.scrapling_scraper.scrape", return_value=self._make_failure()) as mock_scraping:
            crawl.crawl(target)
        mock_fc.assert_called_once_with(target)
        mock_jina.assert_called_once_with(target)
        mock_scraping.assert_called_once_with(target)


# ===========================================================================
# CLI argument parsing tests
# ===========================================================================

class TestCLIArgumentParsing:
    def test_missing_url_exits_with_error(self, capsys):
        with pytest.raises(SystemExit) as exc_info:
            with patch("sys.argv", ["crawl.py"]):
                crawl.main()
        assert exc_info.value.code != 0

    def test_valid_url_succeeds(self, capsys):
        good_result = {"success": True, "markdown": "# Hi\n\n" + _long_str(), "metadata": {}, "error": None}
        with patch("sys.argv", ["crawl.py", "--url", "https://example.com"]), \
             patch("crawl.firecrawl_scraper.scrape", return_value=good_result):
            exit_code = crawl.main()
        assert exit_code == 0
        captured = capsys.readouterr()
        assert "Hi" in captured.out

    def test_all_fail_returns_exit_code_1(self, capsys):
        failure = {"success": False, "markdown": "", "metadata": {}, "error": "fail"}
        with patch("sys.argv", ["crawl.py", "--url", "https://example.com"]), \
             patch("crawl.firecrawl_scraper.scrape", return_value=failure), \
             patch("crawl.jina_reader.fetch", return_value=failure), \
             patch("crawl.scrapling_scraper.scrape", return_value=failure):
            exit_code = crawl.main()
        assert exit_code == 1

    def test_output_goes_to_stdout(self, capsys):
        md = "# Output Test\n\n" + _long_str()
        good_result = {"success": True, "markdown": md, "metadata": {}, "error": None}
        with patch("sys.argv", ["crawl.py", "--url", "https://example.com"]), \
             patch("crawl.firecrawl_scraper.scrape", return_value=good_result):
            crawl.main()
        captured = capsys.readouterr()
        assert md in captured.out

    def test_errors_go_to_stderr(self, capsys):
        failure = {"success": False, "markdown": "", "metadata": {}, "error": "scraper fail"}
        with patch("sys.argv", ["crawl.py", "--url", "https://example.com"]), \
             patch("crawl.firecrawl_scraper.scrape", return_value=failure), \
             patch("crawl.jina_reader.fetch", return_value=failure), \
             patch("crawl.scrapling_scraper.scrape", return_value=failure):
            crawl.main()
        captured = capsys.readouterr()
        assert captured.out == ""
        assert "Error" in captured.err or "failed" in captured.err.lower()


# ===========================================================================
# Content validation tests
# ===========================================================================

class TestContentValidation:
    def test_min_content_length_firecrawl(self):
        """Firecrawl MIN_CONTENT_LENGTH is 100."""
        assert firecrawl_scraper._MIN_CONTENT_LENGTH == 100

    def test_min_content_length_jina(self):
        """Jina Reader MIN_CONTENT_LENGTH is 100."""
        assert jina_reader.MIN_CONTENT_LENGTH == 100

    def test_min_content_length_scrapling(self):
        """Scrapling MIN_CONTENT_LENGTH is 100."""
        assert scrapling_scraper._MIN_CONTENT_LENGTH == 100

    def test_firecrawl_boundary_exactly_at_min(self):
        """Content of exactly MIN_CONTENT_LENGTH chars should be accepted."""
        exactly_min = "x" * firecrawl_scraper._MIN_CONTENT_LENGTH
        mock_result = MagicMock()
        mock_result.markdown = exactly_min
        mock_result.metadata = {}
        mock_app = MagicMock()
        mock_app.scrape.return_value = mock_result
        mock_firecrawl = MagicMock()
        mock_firecrawl.Firecrawl.return_value = mock_app
        with patch.dict("sys.modules", {"firecrawl": mock_firecrawl}):
            result = firecrawl_scraper.scrape("https://example.com")
        # Exactly at boundary: should succeed (>= check)
        assert result["success"] is True

    def test_jina_boundary_one_below_min(self):
        """Content one char below MIN_CONTENT_LENGTH should be rejected."""
        just_below = "x" * (jina_reader.MIN_CONTENT_LENGTH - 1)
        mock_response = MagicMock()
        mock_response.text = just_below
        mock_response.status_code = 200
        mock_response.raise_for_status = MagicMock()
        with patch("jina_reader.httpx.get", return_value=mock_response):
            result = jina_reader.fetch("https://example.com")
        assert result["success"] is False

    def test_result_dict_always_has_required_keys(self):
        """All scraper results should have success, markdown, metadata, error keys."""
        import httpx
        with patch("jina_reader.httpx.get", side_effect=httpx.RequestError("err")):
            result = jina_reader.fetch("https://example.com")
        assert set(result.keys()) >= {"success", "markdown", "metadata", "error"}

        with patch("scrapling.fetchers.Fetcher") as MockFetcher:
            MockFetcher.get.side_effect = RuntimeError("err")
            result = scrapling_scraper.scrape("https://example.com")
        assert set(result.keys()) >= {"success", "markdown", "metadata", "error"}


# ===========================================================================
# domain_router tests
# ===========================================================================

class TestDomainRouter:
    """Unit tests for domain_router.get_tiers()."""

    # --- DEFAULT_TIERS ---
    def test_default_tiers_constant(self):
        """DEFAULT_TIERS must be the canonical 3-tier tuple."""
        assert domain_router.DEFAULT_TIERS == ("firecrawl", "jina", "scrapling")

    # --- Standard URL → all tiers ---
    def test_unknown_domain_returns_all_tiers(self):
        """An unrecognised domain gets the full firecrawl → jina → scrapling chain."""
        tiers = domain_router.get_tiers("https://example.com")
        assert tiers == ("firecrawl", "jina", "scrapling")

    def test_unknown_domain_with_path_returns_all_tiers(self):
        """Path and query string must not affect tier selection."""
        tiers = domain_router.get_tiers("https://docs.python.org/3/library/urllib.parse.html?q=1")
        assert tiers == ("firecrawl", "jina", "scrapling")

    # --- medium.com ---
    def test_medium_com_skips_firecrawl(self):
        """medium.com must skip firecrawl, returning (jina, scrapling)."""
        tiers = domain_router.get_tiers("https://medium.com/some-article")
        assert tiers == ("jina", "scrapling")

    def test_medium_com_subdomain_skips_firecrawl(self):
        """blog.medium.com is a subdomain — must also skip firecrawl."""
        tiers = domain_router.get_tiers("https://blog.medium.com/article")
        assert tiers == ("jina", "scrapling")

    def test_medium_com_deep_subdomain_skips_firecrawl(self):
        """towardsdatascience.com is a separate domain; only exact/suffix match counts."""
        tiers = domain_router.get_tiers("https://towardsdatascience.com/article")
        assert tiers == ("firecrawl", "jina", "scrapling")

    def test_medium_com_order_preserved(self):
        """Remaining tiers must keep the original order (jina before scrapling)."""
        tiers = domain_router.get_tiers("https://medium.com/")
        assert list(tiers).index("jina") < list(tiers).index("scrapling")

    # --- mp.weixin.qq.com ---
    def test_weixin_skips_firecrawl_and_jina(self):
        """mp.weixin.qq.com must skip both firecrawl and jina, leaving only scrapling."""
        tiers = domain_router.get_tiers("https://mp.weixin.qq.com/s/abc123")
        assert tiers == ("scrapling",)

    def test_weixin_subdomain_of_qq_not_matched(self):
        """qq.com itself is not in the rules — must return all tiers."""
        tiers = domain_router.get_tiers("https://qq.com/page")
        assert tiers == ("firecrawl", "jina", "scrapling")

    def test_weixin_other_subdomain_not_matched(self):
        """other.weixin.qq.com is NOT mp.weixin.qq.com — must return all tiers."""
        tiers = domain_router.get_tiers("https://other.weixin.qq.com/page")
        assert tiers == ("firecrawl", "jina", "scrapling")

    # --- Return type ---
    def test_get_tiers_returns_tuple(self):
        """get_tiers() must always return a tuple, never a list or set."""
        result = domain_router.get_tiers("https://example.com")
        assert isinstance(result, tuple)

    def test_get_tiers_never_empty(self):
        """Even the most restrictive rule must leave at least one tier (scrapling)."""
        tiers = domain_router.get_tiers("https://mp.weixin.qq.com/s/test")
        assert len(tiers) >= 1

    # --- DOMAIN_RULES structure ---
    def test_domain_rules_values_are_frozensets(self):
        """All values in DOMAIN_RULES must be frozenset for immutability."""
        for key, value in domain_router.DOMAIN_RULES.items():
            assert isinstance(value, frozenset), f"Rule for {key!r} is not a frozenset"


# ===========================================================================
# crawl.py domain-routing integration tests
# ===========================================================================

class TestCrawlDomainRouting:
    """Integration tests verifying crawl() dispatches according to domain rules."""

    def _make_success(self, label: str) -> dict:
        return {
            "success": True,
            "markdown": f"# From {label}\n\n" + _long_str(),
            "metadata": {},
            "error": None,
        }

    def _make_failure(self, error: str = "failed") -> dict:
        return {"success": False, "markdown": "", "metadata": {}, "error": error}

    def test_medium_com_skips_firecrawl_tries_jina_first(self):
        """For medium.com, crawl() must NOT call firecrawl and must call jina first."""
        jina_result = self._make_success("Jina")
        with patch("crawl.firecrawl_scraper.scrape") as mock_fc, \
             patch("crawl.jina_reader.fetch", return_value=jina_result) as mock_jina, \
             patch("crawl.scrapling_scraper.scrape") as mock_scraping:
            success, markdown = crawl.crawl("https://medium.com/article")
        assert success is True
        mock_fc.assert_not_called()
        mock_jina.assert_called_once_with("https://medium.com/article")
        mock_scraping.assert_not_called()

    def test_medium_com_subdomain_skips_firecrawl(self):
        """blog.medium.com must also skip firecrawl."""
        jina_result = self._make_success("Jina")
        with patch("crawl.firecrawl_scraper.scrape") as mock_fc, \
             patch("crawl.jina_reader.fetch", return_value=jina_result), \
             patch("crawl.scrapling_scraper.scrape"):
            crawl.crawl("https://blog.medium.com/post")
        mock_fc.assert_not_called()

    def test_medium_com_jina_fails_falls_back_to_scrapling(self):
        """medium.com: if jina fails, scrapling is the final fallback."""
        scrapling_result = self._make_success("Scrapling")
        with patch("crawl.firecrawl_scraper.scrape") as mock_fc, \
             patch("crawl.jina_reader.fetch", return_value=self._make_failure()), \
             patch("crawl.scrapling_scraper.scrape", return_value=scrapling_result) as mock_scraping:
            success, markdown = crawl.crawl("https://medium.com/article")
        assert success is True
        assert "Scrapling" in markdown
        mock_fc.assert_not_called()
        mock_scraping.assert_called_once_with("https://medium.com/article")

    def test_weixin_only_uses_scrapling(self):
        """mp.weixin.qq.com must call ONLY scrapling (skip firecrawl and jina)."""
        scrapling_result = self._make_success("Scrapling")
        with patch("crawl.firecrawl_scraper.scrape") as mock_fc, \
             patch("crawl.jina_reader.fetch") as mock_jina, \
             patch("crawl.scrapling_scraper.scrape", return_value=scrapling_result) as mock_scraping:
            success, markdown = crawl.crawl("https://mp.weixin.qq.com/s/abc")
        assert success is True
        mock_fc.assert_not_called()
        mock_jina.assert_not_called()
        mock_scraping.assert_called_once_with("https://mp.weixin.qq.com/s/abc")

    def test_weixin_scrapling_fails_returns_false(self):
        """mp.weixin.qq.com: if scrapling fails, crawl returns (False, '')."""
        with patch("crawl.firecrawl_scraper.scrape") as mock_fc, \
             patch("crawl.jina_reader.fetch") as mock_jina, \
             patch("crawl.scrapling_scraper.scrape", return_value=self._make_failure()):
            success, markdown = crawl.crawl("https://mp.weixin.qq.com/s/abc")
        assert success is False
        assert markdown == ""
        mock_fc.assert_not_called()
        mock_jina.assert_not_called()
