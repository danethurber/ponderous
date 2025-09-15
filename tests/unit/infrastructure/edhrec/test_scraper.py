"""Unit tests for EDHREC scraper."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest
from bs4 import BeautifulSoup

from ponderous.infrastructure.edhrec.exceptions import (
    EDHRECConnectionError,
    EDHRECRateLimitError,
    EDHRECScrapingError,
)
from ponderous.infrastructure.edhrec.models import EDHRECCommander
from ponderous.infrastructure.edhrec.scraper import EDHRECScraper
from ponderous.shared.config import EDHRECConfig


class TestEDHRECScraper:
    """Test suite for EDHRECScraper."""

    @pytest.fixture
    def scraper(self):
        """Create scraper instance for testing."""
        config = EDHRECConfig(
            base_url="https://edhrec.com",
            timeout=5.0,
            max_retries=2,
            retry_delay=0.1,
            rate_limit=10.0,  # 10 requests per second for testing
        )
        return EDHRECScraper(config)

    @pytest.fixture
    def mock_commander_html(self):
        """Mock HTML for commander list page."""
        return """
        <html>
            <body>
                <div class="commanders-container">
                    <div class="commander-tile" data-commander="atraxa-praetors-voice">
                        <a href="/commanders/atraxa-praetors-voice">
                            <h3>Atraxa, Praetors' Voice</h3>
                            <div class="commander-stats">
                                <span class="total-decks">15000</span>
                                <span class="avg-price">$450.75</span>
                                <span class="salt-score">2.5</span>
                                <span class="power-level">8.0</span>
                            </div>
                        </a>
                    </div>
                </div>
            </body>
        </html>
        """

    @pytest.mark.asyncio
    async def test_context_manager_lifecycle(self, scraper):
        """Should handle async context manager lifecycle."""
        with (
            patch.object(
                scraper, "_ensure_session", new_callable=AsyncMock
            ) as mock_ensure,
            patch.object(
                scraper, "_close_session", new_callable=AsyncMock
            ) as mock_close,
        ):
            async with scraper as s:
                assert s is scraper
                mock_ensure.assert_called_once()
            mock_close.assert_called_once()

    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(self, scraper):
        """Should enforce rate limiting between requests."""
        with (
            patch("time.time") as mock_time,
            patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
        ):
            mock_time.side_effect = [0.0, 0.05]  # Second call too soon

            with patch.object(scraper, "_ensure_session", new_callable=AsyncMock):
                mock_response = Mock()
                mock_response.status_code = 200
                mock_response.text = "<html><body></body></html>"

                with patch.object(scraper, "_session") as mock_session:
                    mock_session.get = AsyncMock(return_value=mock_response)

                    # This should trigger rate limiting
                    await scraper._fetch_page("https://example.com")

                    # Should have slept to enforce rate limit
                    mock_sleep.assert_called_once()

    @pytest.mark.asyncio
    async def test_fetch_page_success(self, scraper, mock_commander_html):
        """Should successfully fetch and parse HTML page."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.text = mock_commander_html

        with (
            patch.object(scraper, "_ensure_session", new_callable=AsyncMock),
            patch.object(scraper, "_session") as mock_session,
        ):
            mock_session.get = AsyncMock(return_value=mock_response)

            soup = await scraper._fetch_page("https://edhrec.com/commanders")

            assert isinstance(soup, BeautifulSoup)
            assert soup.find("h3").text == "Atraxa, Praetors' Voice"

    @pytest.mark.asyncio
    async def test_fetch_page_404_error(self, scraper):
        """Should handle 404 errors appropriately."""
        mock_response = Mock()
        mock_response.status_code = 404

        with (
            patch.object(scraper, "_ensure_session", new_callable=AsyncMock),
            patch.object(scraper, "_session") as mock_session,
        ):
            mock_session.get = AsyncMock(return_value=mock_response)

            with pytest.raises(EDHRECScrapingError, match="Page not found"):
                await scraper._fetch_page("https://edhrec.com/nonexistent")

    @pytest.mark.asyncio
    async def test_fetch_page_rate_limit_error(self, scraper):
        """Should handle rate limit errors with backoff."""
        mock_response = Mock()
        mock_response.status_code = 429

        with (
            patch.object(scraper, "_ensure_session", new_callable=AsyncMock),
            patch.object(scraper, "_session") as mock_session,
        ):
            mock_session.get = AsyncMock(return_value=mock_response)

            with pytest.raises(EDHRECRateLimitError):
                await scraper._fetch_page("https://edhrec.com/commanders")

    @pytest.mark.asyncio
    async def test_fetch_page_connection_error_with_retry(self, scraper):
        """Should retry on connection errors."""
        with (
            patch.object(scraper, "_ensure_session", new_callable=AsyncMock),
            patch.object(scraper, "_session") as mock_session,
        ):
            # First call fails, second succeeds
            mock_session.get = AsyncMock(
                side_effect=[
                    httpx.ConnectError("Connection failed"),
                    Mock(status_code=200, text="<html><body>Success</body></html>"),
                ]
            )

            soup = await scraper._fetch_page("https://edhrec.com/commanders")

            assert isinstance(soup, BeautifulSoup)
            assert mock_session.get.call_count == 2

    @pytest.mark.asyncio
    async def test_fetch_page_timeout_exhausted_retries(self, scraper):
        """Should raise error when retries are exhausted."""
        with (
            patch.object(scraper, "_ensure_session", new_callable=AsyncMock),
            patch.object(scraper, "_session") as mock_session,
        ):
            mock_session.get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))

            with pytest.raises(EDHRECConnectionError, match="after 2 retries"):
                await scraper._fetch_page("https://edhrec.com/commanders")

            # Should have tried max_retries + 1 times
            assert mock_session.get.call_count == 3

    @pytest.mark.asyncio
    async def test_get_popular_commanders_success(self, scraper, mock_commander_html):
        """Should successfully scrape popular commanders."""
        with patch.object(scraper, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = BeautifulSoup(mock_commander_html, "html.parser")

            commanders = await scraper.get_popular_commanders(limit=1)

            assert len(commanders) == 1
            assert isinstance(commanders[0], EDHRECCommander)
            assert commanders[0].name == "Atraxa, Praetors' Voice"
            mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_popular_commanders_empty_result(self, scraper):
        """Should handle empty commander list gracefully."""
        empty_html = (
            "<html><body><div class='commanders-container'></div></body></html>"
        )

        with patch.object(scraper, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = BeautifulSoup(empty_html, "html.parser")

            commanders = await scraper.get_popular_commanders(limit=10)

            assert commanders == []

    @pytest.mark.asyncio
    async def test_get_popular_commanders_limit_respected(self, scraper):
        """Should respect the limit parameter."""
        # Create HTML with multiple commanders
        multi_commander_html = """
        <html><body><div class="commanders-container">
            <div class="commander-tile"><a href="/commanders/atraxa"><h3>Atraxa</h3></a></div>
            <div class="commander-tile"><a href="/commanders/thrasios"><h3>Thrasios</h3></a></div>
            <div class="commander-tile"><a href="/commanders/kenrith"><h3>Kenrith</h3></a></div>
        </div></body></html>
        """

        with patch.object(scraper, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = BeautifulSoup(multi_commander_html, "html.parser")

            commanders = await scraper.get_popular_commanders(limit=2)

            assert len(commanders) <= 2

    @pytest.mark.asyncio
    async def test_browser_initialization_and_cleanup(self, scraper):
        """Should properly initialize and cleanup Playwright browser."""
        mock_playwright = AsyncMock()
        mock_browser = AsyncMock()
        mock_playwright.chromium.launch = AsyncMock(return_value=mock_browser)

        with patch(
            "ponderous.infrastructure.edhrec.scraper.async_playwright",
            return_value=mock_playwright,
        ):
            browser = await scraper._ensure_browser(headless=True)

            assert browser is mock_browser
            mock_playwright.chromium.launch.assert_called_once_with(headless=True)

    @pytest.mark.asyncio
    async def test_concurrent_scraping_safety(self, scraper):
        """Should handle concurrent scraping requests safely."""

        async def mock_fetch_delay(*args, **kwargs):
            await asyncio.sleep(0.01)  # Small delay to test concurrency
            return BeautifulSoup("<html><body></body></html>", "html.parser")

        with patch.object(scraper, "_fetch_page", side_effect=mock_fetch_delay):
            # Start multiple concurrent requests
            tasks = [scraper.get_popular_commanders(limit=1) for _ in range(3)]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should complete without exceptions
            for result in results:
                assert not isinstance(result, Exception)
                assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_scraper_error_handling_integration(self, scraper):
        """Should integrate error handling across scraper components."""
        with patch.object(scraper, "_fetch_page", new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = EDHRECConnectionError("Network error")

            with pytest.raises(EDHRECConnectionError, match="Network error"):
                await scraper.get_popular_commanders()

    def test_scraper_configuration_initialization(self):
        """Should initialize with proper configuration."""
        custom_config = EDHRECConfig(
            base_url="https://custom.edhrec.com",
            timeout=10.0,
            max_retries=5,
            retry_delay=0.5,
            rate_limit=2.0,
        )
        scraper = EDHRECScraper(custom_config)

        assert scraper.config.base_url == "https://custom.edhrec.com"
        assert scraper.config.timeout == 10.0
        assert scraper.config.max_retries == 5
        assert scraper.config.retry_delay == 0.5
        assert scraper.config.rate_limit == 2.0

    def test_scraper_default_configuration(self):
        """Should use default configuration when none provided."""
        scraper = EDHRECScraper()

        assert scraper.config is not None
        assert isinstance(scraper.config, EDHRECConfig)
