"""EDHREC web scraper for commander and deck data."""

import asyncio
import logging
import re
import time
from datetime import datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from ponderous.shared.config import EDHRECConfig

from .exceptions import (
    EDHRECConnectionError,
    EDHRECRateLimitError,
    EDHRECScrapingError,
)
from .models import EDHRECCommander, EDHRECScrapingResult

logger = logging.getLogger(__name__)


class EDHRECScraper:
    """Web scraper for EDHREC commander and deck data."""

    def __init__(self, config: EDHRECConfig | None = None) -> None:
        """Initialize EDHREC scraper.

        Args:
            config: EDHREC configuration settings
        """
        self.config = config or EDHRECConfig()
        self._last_request_time = 0.0
        self._session: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "EDHRECScraper":
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._close_session()

    async def _ensure_session(self) -> None:
        """Ensure HTTP session is available."""
        if self._session is None:
            self._session = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers={"User-Agent": self.config.user_agent},
                follow_redirects=True,
            )

    async def _close_session(self) -> None:
        """Close HTTP session."""
        if self._session:
            await self._session.aclose()
            self._session = None

    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests."""
        current_time = time.time()
        time_since_last = current_time - self._last_request_time
        min_interval = 1.0 / self.config.rate_limit

        if time_since_last < min_interval:
            sleep_time = min_interval - time_since_last
            logger.debug(f"Rate limiting: sleeping {sleep_time:.2f}s")
            await asyncio.sleep(sleep_time)

        self._last_request_time = time.time()

    async def _fetch_page(self, url: str, retries: int = 0) -> BeautifulSoup:
        """Fetch and parse a page from EDHREC.

        Args:
            url: URL to fetch
            retries: Number of retries attempted

        Returns:
            BeautifulSoup parsed page

        Raises:
            EDHRECConnectionError: If connection fails
            EDHRECRateLimitError: If rate limited
            EDHRECScrapingError: If scraping fails
        """
        await self._ensure_session()
        await self._rate_limit()

        try:
            logger.debug(f"Fetching {url}")
            if self._session is None:
                raise EDHRECConnectionError("HTTP session not initialized", url)
            response = await self._session.get(url)

            if response.status_code == 429:
                raise EDHRECRateLimitError("Rate limit exceeded", url)
            elif response.status_code == 404:
                raise EDHRECScrapingError(f"Page not found: {url}", url)
            elif response.status_code != 200:
                raise EDHRECScrapingError(
                    f"HTTP {response.status_code}: {response.text}", url
                )

            return BeautifulSoup(response.text, "html.parser")

        except httpx.TimeoutException as e:
            if retries < self.config.max_retries:
                logger.warning(
                    f"Timeout fetching {url}, retrying ({retries + 1}/{self.config.max_retries})"
                )
                await asyncio.sleep(self.config.retry_delay * (retries + 1))
                return await self._fetch_page(url, retries + 1)
            raise EDHRECConnectionError(
                f"Timeout after {retries + 1} attempts", url
            ) from e

        except httpx.ConnectError as e:
            if retries < self.config.max_retries:
                logger.warning(
                    f"Connection error for {url}, retrying ({retries + 1}/{self.config.max_retries})"
                )
                await asyncio.sleep(self.config.retry_delay * (retries + 1))
                return await self._fetch_page(url, retries + 1)
            raise EDHRECConnectionError(
                f"Connection failed after {retries + 1} attempts", url
            ) from e

        except Exception as e:
            raise EDHRECScrapingError(
                f"Unexpected error fetching {url}: {e}", url
            ) from e

    async def get_popular_commanders(self, limit: int = 100) -> list[EDHRECCommander]:
        """Get popular commanders from EDHREC.

        Args:
            limit: Maximum number of commanders to retrieve

        Returns:
            List of popular commanders
        """
        commanders = []
        url = urljoin(self.config.base_url, "/commanders")

        try:
            soup = await self._fetch_page(url)
            commander_links = soup.find_all("a", href=re.compile(r"/commanders/[^/]+$"))

            for i, link in enumerate(commander_links[:limit]):
                if not isinstance(link, Tag):
                    continue

                try:
                    href = link.get("href")
                    if not isinstance(href, str):
                        continue
                    commander_url = urljoin(self.config.base_url, href)
                    commander = await self._parse_commander_page(commander_url)
                    if commander:
                        commanders.append(commander)
                        logger.info(
                            f"Scraped commander {i + 1}/{limit}: {commander.name}"
                        )
                except Exception as e:
                    logger.warning(
                        f"Failed to parse commander from {link.get('href', 'unknown')}: {e}"
                    )
                    continue

        except Exception as e:
            logger.error(f"Failed to get popular commanders: {e}")
            raise EDHRECScrapingError(f"Failed to scrape commanders list: {e}") from e

        return commanders

    async def _parse_commander_page(self, url: str) -> EDHRECCommander | None:
        """Parse a commander page to extract data.

        Args:
            url: Commander page URL

        Returns:
            EDHRECCommander object or None if parsing fails
        """
        try:
            soup = await self._fetch_page(url)

            # Extract commander name from title or header
            title_elem = soup.find("h1") or soup.find("title")
            if not title_elem:
                logger.warning(f"No title found for commander page: {url}")
                return None

            name = self._clean_text(title_elem.get_text())
            if "EDHREC" in name:
                # Clean up title like "Edgar Markov - EDHREC"
                name = name.split(" - ")[0].strip()

            # Extract URL slug from URL
            url_slug = urlparse(url).path.split("/")[-1]

            # Parse color identity from page
            color_identity = self._extract_color_identity(soup)

            # Parse deck count
            total_decks = self._extract_deck_count(soup)

            # Parse popularity rank (placeholder - would need more sophisticated parsing)
            popularity_rank = 999  # Default high rank

            # Parse average deck price (placeholder)
            avg_deck_price = 250.0  # Default price

            # Parse salt score (placeholder)
            salt_score = 2.5  # Default moderate salt

            # Parse power level (placeholder)
            power_level = 6.0  # Default power level

            return EDHRECCommander(
                name=name,
                url_slug=url_slug,
                color_identity=color_identity,
                total_decks=total_decks,
                popularity_rank=popularity_rank,
                avg_deck_price=avg_deck_price,
                salt_score=salt_score,
                power_level=power_level,
            )

        except Exception as e:
            logger.warning(f"Failed to parse commander page {url}: {e}")
            return None

    def _extract_color_identity(self, soup: BeautifulSoup) -> str:
        """Extract color identity from commander page.

        Args:
            soup: Parsed page content

        Returns:
            Color identity string (e.g., "RWB", "U", "C")
        """
        # Look for color symbols in common locations
        color_symbols = soup.find_all("img", src=re.compile(r"mana.*\.(png|svg)"))
        colors = set()

        for symbol in color_symbols:
            if not isinstance(symbol, Tag):
                continue
            src_attr = symbol.get("src")
            if not isinstance(src_attr, str):
                continue
            src = src_attr.lower()
            if "/w." in src or "white" in src:
                colors.add("W")
            elif "/u." in src or "blue" in src:
                colors.add("U")
            elif "/b." in src or "black" in src:
                colors.add("B")
            elif "/r." in src or "red" in src:
                colors.add("R")
            elif "/g." in src or "green" in src:
                colors.add("G")

        if not colors:
            return "C"  # Colorless

        return "".join(sorted(colors))

    def _extract_deck_count(self, soup: BeautifulSoup) -> int:
        """Extract total deck count from commander page.

        Args:
            soup: Parsed page content

        Returns:
            Number of decks featuring this commander
        """
        # Look for deck count indicators
        deck_count_patterns = [
            r"(\d+(?:,\d+)*)\s*decks?",
            r"(\d+(?:,\d+)*)\s*lists?",
        ]

        page_text = soup.get_text()
        for pattern in deck_count_patterns:
            match = re.search(pattern, page_text, re.IGNORECASE)
            if match:
                count_str = match.group(1).replace(",", "")
                try:
                    return int(count_str)
                except ValueError:
                    continue

        return 1  # Default to 1 if no count found

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content.

        Args:
            text: Raw text to clean

        Returns:
            Cleaned text
        """
        return " ".join(text.strip().split())

    async def scrape_commanders_batch(
        self,
        limit: int = 50,
        start_rank: int = 1,  # noqa: ARG002
    ) -> EDHRECScrapingResult:
        """Scrape a batch of commanders with comprehensive results.

        Args:
            limit: Number of commanders to scrape
            start_rank: Starting popularity rank

        Returns:
            Scraping result with metrics
        """
        start_time = time.time()
        commanders_found = 0
        errors: list[str] = []
        warnings: list[str] = []

        try:
            commanders = await self.get_popular_commanders(limit)
            commanders_found = len(commanders)

            logger.info(f"Successfully scraped {commanders_found} commanders")

        except Exception as e:
            error_msg = f"Failed to scrape commanders: {e}"
            logger.error(error_msg)
            errors.append(error_msg)

        processing_time = time.time() - start_time

        return EDHRECScrapingResult(
            success=len(errors) == 0,
            commanders_found=commanders_found,
            decks_found=0,  # Will implement deck scraping separately
            cards_found=0,  # Will implement card scraping separately
            processing_time_seconds=processing_time,
            errors=errors,
            warnings=warnings,
            scraped_at=datetime.now(),
        )
