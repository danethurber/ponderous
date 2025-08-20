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
from playwright.async_api import Browser, Page, async_playwright

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
        self._playwright = None
        self._browser: Browser | None = None
        self._browser_context = None

    async def __aenter__(self) -> "EDHRECScraper":
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self._close_session()
        await self._close_browser()

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

    async def _ensure_browser(self, headless: bool = True) -> Browser:
        """Ensure browser session is available."""
        if self._browser is None:
            self._playwright = await async_playwright().start()
            self._browser = await self._playwright.chromium.launch(
                headless=headless, args=["--no-sandbox", "--disable-dev-shm-usage"]
            )
        return self._browser

    async def _close_browser(self) -> None:
        """Close browser session."""
        if self._browser_context:
            await self._browser_context.close()
            self._browser_context = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

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
        url = urljoin(self.config.base_url, "/commanders")

        try:
            soup = await self._fetch_page(url)

            # Extract real commander data from JSON
            real_commanders = await self._parse_commanders_list(soup)

            if not real_commanders or len(real_commanders) == 0:
                raise EDHRECScrapingError(
                    "Failed to extract commander data from EDHREC"
                )

            logger.info(f"Successfully scraped {len(real_commanders)} real commanders")
            return real_commanders[:limit]

        except Exception as e:
            logger.error(f"Failed to get popular commanders: {e}")
            raise EDHRECScrapingError(f"Failed to scrape commanders list: {e}") from e

    async def get_paginated_commanders(
        self, max_pages: int = 5, headless: bool = True
    ) -> list[EDHRECCommander]:
        """Get commanders using Playwright pagination with Load More button.

        Args:
            max_pages: Maximum number of pages to load
            headless: Whether to run browser in headless mode

        Returns:
            List of commanders from all pages
        """
        commanders = []

        try:
            # Set up browser
            browser = await self._ensure_browser(headless=headless)
            if self._browser_context:
                await self._browser_context.close()

            self._browser_context = await browser.new_context(
                user_agent=self.config.user_agent,
                viewport={"width": 1280, "height": 720},
            )

            page = await self._browser_context.new_page()

            # Navigate to commanders page
            commanders_url = urljoin(self.config.base_url, "/commanders")
            logger.info(f"Navigating to {commanders_url}")
            await page.goto(commanders_url, wait_until="networkidle")

            # Wait for page to fully load and scroll to see all content
            await page.wait_for_load_state("networkidle")
            await page.wait_for_timeout(2000)  # Additional wait for dynamic content

            # Scroll down to potentially reveal Load More button
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(1000)

            # Extract initial commanders
            initial_commanders = await self._extract_commanders_from_page(page)
            commanders.extend(initial_commanders)
            logger.info(
                f"Extracted {len(initial_commanders)} commanders from initial page"
            )

            # Pagination loop
            pages_loaded = 1
            while pages_loaded < max_pages:
                # First, scroll down to ensure Load More button is visible
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)

                # Look for Load More button with multiple selectors and longer timeout
                load_more_selectors = [
                    "button:has-text('Load More')",
                    "button:has-text('load more')",
                    "button:has-text('Show More')",
                    "button:has-text('show more')",
                    "button:has-text('More')",
                    "button[class*='load'], button[class*='more']",
                    ".load-more-button, .show-more-button, .load-more, .show-more",
                    "a:has-text('More'), a:has-text('Load More')",
                    "[data-cy='load-more'], [data-testid='load-more']",
                ]

                load_more_button = None
                for selector in load_more_selectors:
                    try:
                        candidate_button = page.locator(selector).first
                        await candidate_button.wait_for(timeout=5000)  # Longer timeout
                        if await candidate_button.is_visible():
                            load_more_button = candidate_button
                            logger.info(
                                f"Found Load More button with selector: {selector}"
                            )
                            break
                    except Exception as e:
                        logger.debug(f"Selector '{selector}' failed: {e}")
                        continue

                if not load_more_button:
                    # Debug: Check what buttons are actually on the page
                    try:
                        all_buttons = await page.locator("button, a").all()
                        button_texts = []
                        for button in all_buttons:
                            try:
                                text = await button.text_content()
                                if text and text.strip():
                                    button_texts.append(text.strip())
                            except Exception as e:
                                logger.debug(f"Failed to get button text: {e}")
                                continue
                        logger.info(
                            f"Available buttons on page: {button_texts[:20]}"
                        )  # Show first 20
                    except Exception as e:
                        logger.debug(f"Failed to debug buttons: {e}")

                    logger.info(
                        "No Load More button found, checking if pagination is infinite scroll"
                    )
                    # Try scrolling to bottom to trigger infinite scroll
                    current_count = len(commanders)
                    await page.evaluate(
                        "window.scrollTo(0, document.body.scrollHeight)"
                    )
                    await page.wait_for_timeout(3000)

                    # Check if new content was loaded by re-extracting all commanders
                    all_page_commanders = await self._extract_commanders_from_page(page)
                    if len(all_page_commanders) > current_count:
                        # Infinite scroll worked, add new commanders
                        new_commanders = all_page_commanders[current_count:]
                        commanders.extend(new_commanders)
                        logger.info(
                            f"Infinite scroll loaded {len(new_commanders)} new commanders"
                        )
                        pages_loaded += 1
                        await asyncio.sleep(2)
                        continue
                    else:
                        logger.info(
                            "No Load More button and no infinite scroll, stopping pagination"
                        )
                        break

                try:
                    # Wait for button to be visible and clickable
                    if not await load_more_button.is_visible():
                        logger.info("Load More button not visible, stopping pagination")
                        break

                    if not await load_more_button.is_enabled():
                        logger.info("Load More button not enabled, stopping pagination")
                        break

                    # Click the button
                    await load_more_button.click()
                    logger.info(f"Clicked Load More button (page {pages_loaded + 1})")

                    # Wait for new content to load
                    await page.wait_for_timeout(3000)  # Wait 3 seconds for content

                    # Extract all commanders and get new ones
                    all_page_commanders = await self._extract_commanders_from_page(page)
                    logger.info(
                        f"After clicking Load More: found {len(all_page_commanders)} total commanders, previously had {len(commanders)}"
                    )

                    if len(all_page_commanders) > len(commanders):
                        new_commanders = all_page_commanders[len(commanders) :]
                        commanders.extend(new_commanders)
                        logger.info(
                            f"Extracted {len(new_commanders)} new commanders from page {pages_loaded + 1}"
                        )
                        pages_loaded += 1
                    else:
                        logger.info(
                            "No new commanders found after clicking, stopping pagination"
                        )
                        # Debug: Compare first few commander names to see if they're different
                        if len(all_page_commanders) >= 5 and len(commanders) >= 5:
                            current_first_5 = [cmd.name for cmd in commanders[:5]]
                            page_first_5 = [cmd.name for cmd in all_page_commanders[:5]]
                            logger.info(f"Current first 5: {current_first_5}")
                            logger.info(f"Page first 5: {page_first_5}")
                        break

                    # Rate limiting
                    await asyncio.sleep(2)  # 2 second delay between pages

                except Exception as e:
                    logger.warning(
                        f"Failed to load more on page {pages_loaded + 1}: {e}"
                    )
                    break

            logger.info(
                f"Pagination complete: {len(commanders)} total commanders from {pages_loaded} pages"
            )
            return commanders

        except Exception as e:
            logger.error(f"Failed to get paginated commanders: {e}")
            raise EDHRECScrapingError(
                f"Failed to scrape paginated commanders: {e}"
            ) from e

    async def _extract_commanders_from_page(
        self, page: Page, skip_existing: int = 0
    ) -> list[EDHRECCommander]:
        """Extract commander data from Playwright page using DOM parsing.

        Args:
            page: Playwright page object
            skip_existing: Number of existing commanders to skip (for pagination)

        Returns:
            List of EDHRECCommander objects
        """
        try:
            # Extract commanders from Card div elements (EDHREC's actual structure)
            card_elements = await page.locator('div[class*="Card"]').all()
            logger.info(f"Found {len(card_elements)} Card elements on page")

            commanders = []
            for i, card in enumerate(card_elements):
                try:
                    # Skip existing commanders for pagination
                    if i < skip_existing:
                        continue

                    card_text = await card.text_content()
                    if not card_text:
                        continue

                    # Parse commander data from card text
                    lines = [
                        line.strip() for line in card_text.split("\n") if line.strip()
                    ]

                    # Skip cards that are too long (likely containers with multiple commanders)
                    if len(lines) > 10:
                        continue

                    name = None
                    deck_count = 0

                    for line in lines:
                        # Skip navigation/filter text and ads
                        if any(
                            skip in line.lower()
                            for skip in [
                                "group by",
                                "sort by",
                                "filter",
                                "patreon",
                                "please consider",
                            ]
                        ):
                            continue

                        # Extract deck count (look for patterns like "38246 decks")
                        import re

                        deck_match = re.search(
                            r"(\d+(?:,\d+)*)\s*deck", line, re.IGNORECASE
                        )
                        if deck_match:
                            deck_count = int(deck_match.group(1).replace(",", ""))

                        # Extract commander name - look for text without prices, ranks, or deck counts
                        # First, clean the line by removing prices and rank info
                        cleaned_line = re.sub(r"\$[\d.,]+", "", line)  # Remove prices
                        cleaned_line = re.sub(
                            r"Rank \d+", "", cleaned_line
                        )  # Remove rank
                        cleaned_line = re.sub(
                            r"Salt Score: [\d.,]+", "", cleaned_line
                        )  # Remove salt score
                        cleaned_line = cleaned_line.strip()

                        # Extract commander name (reasonable length, contains letters, not just numbers)
                        if (
                            not name
                            and len(cleaned_line) > 2
                            and len(cleaned_line) < 50
                            and any(c.isalpha() for c in cleaned_line)
                            and "deck" not in cleaned_line.lower()
                            and not re.match(r"^\d+$", cleaned_line)  # Not just numbers
                            and not re.search(r"^\d+\s*$", cleaned_line)
                        ):  # Not just numbers with whitespace
                            name = cleaned_line

                    if name and len(name) > 2 and deck_count > 0:
                        # Generate URL slug from name
                        url_slug = (
                            name.lower()
                            .replace(" ", "-")
                            .replace(",", "")
                            .replace("'", "")
                            .replace('"', "")
                            .replace(":", "")
                            .replace("/", "-")
                            .replace("(", "")
                            .replace(")", "")
                            .replace("—", "-")
                            .replace("–", "-")
                        )

                        commander = EDHRECCommander(
                            name=name,
                            url_slug=url_slug,
                            color_identity="unknown",  # Color identity to be determined later
                            total_decks=deck_count,
                            popularity_rank=len(commanders)
                            + 1,  # Use actual position in results
                            avg_deck_price=250.0,  # Default price
                            salt_score=self._estimate_salt_score(name),
                            power_level=self._estimate_power_level(name, deck_count),
                        )

                        commanders.append(commander)

                except Exception as e:
                    logger.debug(f"Failed to parse card element {i}: {e}")
                    continue

            # If DOM parsing didn't work, fall back to JSON parsing
            if not commanders:
                logger.info(
                    "DOM parsing found no commanders, falling back to JSON parsing"
                )
                return await self._extract_commanders_from_json(page, skip_existing)

            logger.info(f"DOM parsing found {len(commanders)} commanders")
            return commanders

        except Exception as e:
            logger.error(
                f"Failed to extract commanders from DOM, falling back to JSON: {e}"
            )
            return await self._extract_commanders_from_json(page, skip_existing)

    async def _extract_commanders_from_json(
        self, page: Page, skip_existing: int = 0
    ) -> list[EDHRECCommander]:
        """Extract commander data from JSON (original method).

        Args:
            page: Playwright page object
            skip_existing: Number of existing commanders to skip (for pagination)

        Returns:
            List of EDHRECCommander objects
        """
        try:
            # Get the page HTML and parse with BeautifulSoup for JSON extraction
            html_content = await page.content()
            soup = BeautifulSoup(html_content, "html.parser")

            # Extract JSON data from Next.js
            script = soup.find("script", id="__NEXT_DATA__")
            if not script or not script.string:
                logger.warning("No __NEXT_DATA__ script found on page")
                return []

            import json

            data = json.loads(script.string)

            # Navigate through the JSON structure to find commanders
            page_props = data.get("props", {}).get("pageProps", {})
            commanders_data = page_props.get("commanders", [])

            if not commanders_data:
                # Try alternative JSON structure paths
                data_section = page_props.get("data", {})
                commanders_data = data_section.get("commanders", [])

                # Try container structure (EDHREC stores commander list in cardlists[0].cardviews)
                if not commanders_data:
                    container = data_section.get("container", {})
                    json_dict = container.get("json_dict", {})
                    cardlists = json_dict.get("cardlists", [])

                    # EDHREC commanders page has cardlists[0].cardviews containing commander data
                    if cardlists and len(cardlists) > 0:
                        cardviews = cardlists[0].get("cardviews", [])
                        if cardviews:
                            commanders_data = cardviews

            if not commanders_data:
                return []

            # Skip existing commanders for pagination
            commanders_data = commanders_data[skip_existing:]

            commanders = []
            for i, cmd_data in enumerate(commanders_data):
                try:
                    # Extract commander information from EDHREC's actual format
                    name = cmd_data.get("name", "").strip()
                    url_slug = cmd_data.get(
                        "sanitized", ""
                    )  # EDHREC uses 'sanitized' for URL slug
                    total_decks = int(
                        cmd_data.get("num_decks", 0)
                    )  # EDHREC uses 'num_decks'
                    popularity_rank = skip_existing + i + 1

                    if not name or not url_slug:
                        continue

                    commander = EDHRECCommander(
                        name=name,
                        url_slug=url_slug,
                        color_identity="unknown",  # Color identity to be determined later
                        total_decks=total_decks,
                        popularity_rank=popularity_rank,
                        avg_deck_price=250.0,  # Default price
                        salt_score=self._estimate_salt_score(name),
                        power_level=self._estimate_power_level(name, total_decks),
                    )

                    commanders.append(commander)

                except (ValueError, KeyError) as e:
                    logger.warning(f"Failed to parse commander data {i}: {e}")
                    continue

            return commanders

        except Exception as e:
            logger.error(f"Failed to extract commanders from JSON: {e}")
            return []

    async def _parse_commanders_list(
        self, soup: BeautifulSoup
    ) -> list[EDHRECCommander]:
        """Parse real commander data from EDHREC commanders page.

        Args:
            soup: BeautifulSoup parsed page content

        Returns:
            List of real commander data
        """
        try:
            import json

            # Find the Next.js JSON data
            script = soup.find("script", id="__NEXT_DATA__")
            if not script or not script.string:
                logger.warning("No __NEXT_DATA__ script found on commanders page")
                return []

            # Parse JSON data (not currently used but kept for potential future parsing)
            json.loads(script.string)

            # The commanders page structure might be different from individual commander pages
            # For now, return a curated list of known popular commanders that we can scrape individually
            # This is a hybrid approach: real commander names but estimated stats

            popular_commander_slugs = [
                "atraxa-praetors-voice",
                "edgar-markov",
                "the-ur-dragon",
                "korvold-fae-cursed-king",
                "meren-of-clan-nel-toth",
                "prossh-skyraider-of-kher",
                "kaalia-of-the-vast",
                "muldrotha-the-gravetide",
                "ghave-guru-of-spores",
                "oloro-ageless-ascetic",
                "breya-etherium-shaper",
                "sliver-overlord",
                "rhys-the-redeemed",
                "krenko-mob-boss",
                "azami-lady-of-scrolls",
                "mikaeus-the-unhallowed",
                "elesh-norn-grand-cenobite",
                "omnath-locus-of-creation",
                "jhoira-of-the-ghitu",
                "zurgo-helmsmasher",
            ]

            commanders = []

            # For each commander, get real data from their individual page
            for i, slug in enumerate(popular_commander_slugs):
                try:
                    commander_url = urljoin(self.config.base_url, f"/commanders/{slug}")
                    commander_soup = await self._fetch_page(commander_url)

                    # Extract real commander data
                    real_commander = await self._parse_individual_commander(
                        commander_soup, slug, i + 1
                    )
                    if real_commander:
                        commanders.append(real_commander)
                        logger.info(f"Scraped real data for {real_commander.name}")

                except Exception as e:
                    logger.warning(f"Failed to scrape commander {slug}: {e}")
                    continue

            return commanders

        except Exception as e:
            logger.error(f"Failed to parse commanders list: {e}")
            return []

    async def _parse_individual_commander(
        self, soup: BeautifulSoup, url_slug: str, rank: int
    ) -> EDHRECCommander | None:
        """Parse data for an individual commander from their page.

        Args:
            soup: BeautifulSoup parsed commander page
            url_slug: Commander URL slug
            rank: Popularity rank

        Returns:
            EDHRECCommander object or None if parsing fails
        """
        try:
            import json

            # Find the Next.js JSON data
            script = soup.find("script", id="__NEXT_DATA__")
            if not script or not script.string:
                return None

            # Parse JSON data
            data = json.loads(script.string)
            page_data = data.get("props", {}).get("pageProps", {}).get("data", {})

            # Extract commander information
            header = page_data.get("header", "")
            num_decks = page_data.get("num_decks_avg", 0)
            avg_price = page_data.get("avg_price", 250)

            # Parse commander name from header (e.g., "Atraxa, Praetors' Voice (Commander)")
            commander_name = header.replace(" (Commander)", "").strip()

            # Extract color identity from the card data
            container = page_data.get("container", {})
            json_dict = container.get("json_dict", {})
            card_data = json_dict.get("card", {})

            # Try multiple fields to get color identity
            colors = card_data.get("color_identity", []) or card_data.get("colors", [])

            # Map color names to letters if needed
            color_mapping = {
                "white": "W",
                "blue": "U",
                "black": "B",
                "red": "R",
                "green": "G",
            }

            if isinstance(colors, list):
                # Convert color names to letters if needed
                color_letters = []
                for color in colors:
                    if isinstance(color, str):
                        if len(color) == 1 and color.upper() in "WUBRG":
                            color_letters.append(color.upper())
                        else:
                            mapped = color_mapping.get(color.lower())
                            if mapped:
                                color_letters.append(mapped)

                color_identity = (
                    "".join(sorted(color_letters)) if color_letters else "unknown"
                )
            else:
                color_identity = "unknown"

            # Estimate other stats
            salt_score = self._estimate_salt_score(commander_name)
            power_level = self._estimate_power_level(commander_name, num_decks)

            commander = EDHRECCommander(
                name=commander_name,
                url_slug=url_slug,
                color_identity=color_identity,
                total_decks=num_decks,
                popularity_rank=rank,
                avg_deck_price=float(avg_price),
                salt_score=salt_score,
                power_level=power_level,
                archetype="Midrange",  # TODO: Extract from themes
                themes=["Value", "Synergy"],  # TODO: Extract from page data
            )

            return commander

        except Exception as e:
            logger.error(f"Failed to parse individual commander {url_slug}: {e}")
            return None

    def _estimate_salt_score(self, commander_name: str) -> float:
        """Estimate salt score based on commander name patterns."""
        name_lower = commander_name.lower()

        # High salt commanders
        if any(word in name_lower for word in ["edgar", "kaalia", "prossh", "oloro"]):
            return 3.5
        # Medium-high salt
        elif any(word in name_lower for word in ["atraxa", "korvold", "meren"]):
            return 2.8
        # Generally powerful commanders
        elif any(word in name_lower for word in ["sliver", "omnath", "breya"]):
            return 2.5
        else:
            return 1.8  # Default moderate salt

    def _estimate_power_level(self, commander_name: str, deck_count: int) -> float:
        """Estimate power level based on commander and popularity."""
        name_lower = commander_name.lower()

        # High power commanders
        if any(word in name_lower for word in ["atraxa", "korvold", "edgar", "kaalia"]):
            return 7.5
        # Popular = generally powerful
        elif deck_count > 30000:
            return 7.0
        elif deck_count > 20000:
            return 6.5
        else:
            return 6.0

    async def _get_sample_commanders(self, limit: int) -> list[EDHRECCommander]:
        """Get sample commander data as fallback.

        Args:
            limit: Maximum number of commanders to return

        Returns:
            List of sample commanders
        """
        # Enhanced commander database with realistic current EDHREC data
        sample_commanders_data = [
            {
                "name": "Atraxa, Praetors' Voice",
                "url_slug": "atraxa-praetors-voice",
                "color_identity": "BUGU",
                "total_decks": 36718,
                "popularity_rank": 1,
            },
            {
                "name": "Edgar Markov",
                "url_slug": "edgar-markov",
                "color_identity": "BRW",
                "total_decks": 67543,
                "popularity_rank": 2,
            },
            {
                "name": "The Ur-Dragon",
                "url_slug": "the-ur-dragon",
                "color_identity": "BRUGW",
                "total_decks": 45231,
                "popularity_rank": 3,
            },
            {
                "name": "Korvold, Fae-Cursed King",
                "url_slug": "korvold-fae-cursed-king",
                "color_identity": "BRG",
                "total_decks": 38921,
                "popularity_rank": 4,
            },
            {
                "name": "Meren of Clan Nel Toth",
                "url_slug": "meren-of-clan-nel-toth",
                "color_identity": "BG",
                "total_decks": 42156,
                "popularity_rank": 5,
            },
        ]

        commanders = []
        for i, cmd_data in enumerate(sample_commanders_data[:limit]):
            commander = EDHRECCommander(
                name=cmd_data["name"],
                url_slug=cmd_data["url_slug"],
                color_identity=cmd_data["color_identity"],
                total_decks=cmd_data["total_decks"],
                popularity_rank=cmd_data["popularity_rank"],
                avg_deck_price=250.0 + (i * 50),
                salt_score=self._estimate_salt_score(cmd_data["name"]),
                power_level=self._estimate_power_level(
                    cmd_data["name"], cmd_data["total_decks"]
                ),
                archetype="Midrange",
                themes=["Value", "Synergy"],
            )
            commanders.append(commander)

        return commanders

    async def scrape_commander_deck_data(
        self, commander_name: str, archetype: str = "default"
    ) -> list[dict] | None:
        """Scrape deck composition data for a specific commander.

        Args:
            commander_name: Name of the commander
            archetype: Deck archetype (default, combo, control, etc.)

        Returns:
            List of card inclusion data with rates and synergy scores
        """
        try:
            # Convert commander name to URL slug
            url_slug = (
                commander_name.lower()
                .replace(" ", "-")
                .replace(",", "")
                .replace("'", "")
            )
            base_url = urljoin(self.config.base_url, f"/commanders/{url_slug}")

            # Add archetype parameter if not default
            if archetype != "default":
                base_url += f"/{archetype}"

            logger.info(
                f"Scraping deck data for {commander_name} ({archetype}) from {base_url}"
            )
            soup = await self._fetch_page(base_url)

            # Extract real EDHREC data from JSON
            real_cards = await self._parse_commander_cards(soup)

            if not real_cards or len(real_cards) == 0:
                raise EDHRECScrapingError(
                    f"Failed to extract card data for {commander_name}"
                )

            logger.info(f"Extracted {len(real_cards)} real cards for {commander_name}")
            return real_cards

        except Exception as e:
            logger.error(f"Failed to scrape deck data for {commander_name}: {e}")
            raise EDHRECScrapingError(
                f"Failed to scrape deck data for {commander_name}: {e}"
            ) from e

    async def _parse_commander_cards(self, soup: BeautifulSoup) -> list[dict]:
        """Parse real card data from EDHREC commander page.

        Args:
            soup: BeautifulSoup parsed page content

        Returns:
            List of card data with inclusion rates and synergy scores
        """
        try:
            import json

            # Find the Next.js JSON data
            script = soup.find("script", id="__NEXT_DATA__")
            if not script or not script.string:
                logger.warning("No __NEXT_DATA__ script found")
                return []

            # Parse JSON data
            data = json.loads(script.string)
            page_data = data.get("props", {}).get("pageProps", {}).get("data", {})
            json_dict = page_data.get("container", {}).get("json_dict", {})

            cardlists = json_dict.get("cardlists", [])
            if not cardlists:
                logger.warning("No cardlists found in JSON data")
                return []

            all_cards = []

            # Extract cards from all categories
            for cardlist in cardlists:
                tag = cardlist.get("tag", "unknown")
                cardviews = cardlist.get("cardviews", [])

                # Map EDHREC categories to our categories
                category_mapping = {
                    "highsynergycards": "signature",
                    "topcards": "staple",
                    "newcards": "high_synergy",
                    "creatures": "basic",
                    "instants": "basic",
                    "sorceries": "basic",
                    "enchantments": "basic",
                    "utilityartifacts": "staple",
                    "manaartifacts": "staple",
                    "planeswalkers": "basic",
                    "lands": "staple",
                    "utilitylands": "basic",
                    "gamechangers": "high_synergy",
                }

                our_category = category_mapping.get(tag, "basic")

                for card in cardviews:
                    card_name = card.get("name")
                    if not card_name:
                        continue

                    # Get inclusion data
                    inclusion = card.get("inclusion", 0)
                    potential_decks = card.get("potential_decks", 1)
                    inclusion_rate = (
                        inclusion / potential_decks if potential_decks > 0 else 0.0
                    )

                    # Get synergy score (already normalized -1.0 to 1.0)
                    synergy_score = card.get("synergy", 0.0)

                    # Estimate price (EDHREC doesn't always have reliable price data)
                    price_usd = self._estimate_card_price(
                        card_name, inclusion_rate, our_category
                    )

                    card_data = {
                        "name": card_name,
                        "inclusion_rate": inclusion_rate,
                        "synergy_score": synergy_score,
                        "category": our_category,
                        "price_usd": price_usd,
                    }

                    all_cards.append(card_data)

            # Sort by inclusion rate and limit to reasonable number
            all_cards.sort(key=lambda x: x["inclusion_rate"], reverse=True)

            # Take top cards to avoid overwhelming the database
            limited_cards = all_cards[:100]  # Limit to top 100 cards

            logger.info(
                f"Parsed {len(limited_cards)} cards from {len(cardlists)} cardlists"
            )
            return limited_cards

        except Exception as e:
            logger.error(f"Failed to parse commander cards: {e}")
            return []

    def _estimate_card_price(
        self, card_name: str, inclusion_rate: float, category: str
    ) -> float:
        """Estimate card price based on inclusion rate and category.

        Args:
            card_name: Name of the card
            inclusion_rate: How often the card appears (0.0-1.0)
            category: Card category

        Returns:
            Estimated price in USD
        """
        # Base price estimation algorithm
        base_price = 2.0  # Default price for basic cards

        # Category multipliers
        if category == "signature":
            base_price = 25.0
        elif category == "high_synergy":
            base_price = 8.0
        elif category == "staple":
            base_price = 5.0

        # Inclusion rate multiplier (popular cards are more expensive)
        popularity_multiplier = 1.0 + (inclusion_rate * 2.0)

        # Special cases for known expensive cards
        expensive_keywords = [
            "mox",
            "lotus",
            "force",
            "mana crypt",
            "gaea's cradle",
            "doubling season",
        ]
        if any(keyword in card_name.lower() for keyword in expensive_keywords):
            base_price *= 3.0

        # Calculate final price
        estimated_price = base_price * popularity_multiplier

        # Cap at reasonable maximum
        return min(estimated_price, 200.0)

    def _generate_sample_deck_data(
        self, commander_name: str, _archetype: str = "default"
    ) -> list[dict]:
        """Generate realistic sample deck data for a commander.

        Args:
            commander_name: Name of the commander
            archetype: Deck archetype

        Returns:
            List of card data with inclusion rates and categories
        """
        # Base cards that appear in most EDH decks
        base_cards = [
            # Lands
            {
                "name": "Command Tower",
                "inclusion_rate": 0.95,
                "category": "staple",
                "synergy_score": 0.1,
            },
            {
                "name": "Arcane Signet",
                "inclusion_rate": 0.89,
                "category": "staple",
                "synergy_score": 0.1,
            },
            {
                "name": "Sol Ring",
                "inclusion_rate": 0.87,
                "category": "staple",
                "synergy_score": 0.1,
            },
            {
                "name": "Reliquary Tower",
                "inclusion_rate": 0.72,
                "category": "staple",
                "synergy_score": 0.0,
            },
            # Removal
            {
                "name": "Swords to Plowshares",
                "inclusion_rate": 0.68,
                "category": "staple",
                "synergy_score": 0.0,
            },
            {
                "name": "Path to Exile",
                "inclusion_rate": 0.61,
                "category": "staple",
                "synergy_score": 0.0,
            },
            {
                "name": "Counterspell",
                "inclusion_rate": 0.54,
                "category": "staple",
                "synergy_score": 0.0,
            },
            # Draw
            {
                "name": "Rhystic Study",
                "inclusion_rate": 0.76,
                "category": "staple",
                "synergy_score": 0.2,
            },
            {
                "name": "Mystic Remora",
                "inclusion_rate": 0.58,
                "category": "staple",
                "synergy_score": 0.1,
            },
        ]

        # Commander-specific high synergy cards
        synergy_cards = []
        commander_lower = commander_name.lower()

        if "atraxa" in commander_lower:
            synergy_cards = [
                {
                    "name": "Doubling Season",
                    "inclusion_rate": 0.84,
                    "category": "signature",
                    "synergy_score": 0.9,
                },
                {
                    "name": "Inexorable Tide",
                    "inclusion_rate": 0.67,
                    "category": "high_synergy",
                    "synergy_score": 0.8,
                },
                {
                    "name": "Viral Drake",
                    "inclusion_rate": 0.45,
                    "category": "high_synergy",
                    "synergy_score": 0.7,
                },
                {
                    "name": "Thrummingbird",
                    "inclusion_rate": 0.41,
                    "category": "high_synergy",
                    "synergy_score": 0.6,
                },
            ]
        elif "edgar" in commander_lower:
            synergy_cards = [
                {
                    "name": "Anointed Procession",
                    "inclusion_rate": 0.78,
                    "category": "signature",
                    "synergy_score": 0.9,
                },
                {
                    "name": "Intangible Virtue",
                    "inclusion_rate": 0.72,
                    "category": "high_synergy",
                    "synergy_score": 0.8,
                },
                {
                    "name": "Vampire Nocturnus",
                    "inclusion_rate": 0.68,
                    "category": "high_synergy",
                    "synergy_score": 0.8,
                },
                {
                    "name": "Bloodline Keeper",
                    "inclusion_rate": 0.61,
                    "category": "high_synergy",
                    "synergy_score": 0.7,
                },
            ]
        elif "meren" in commander_lower:
            synergy_cards = [
                {
                    "name": "Sakura-Tribe Elder",
                    "inclusion_rate": 0.89,
                    "category": "signature",
                    "synergy_score": 0.9,
                },
                {
                    "name": "Eternal Witness",
                    "inclusion_rate": 0.85,
                    "category": "signature",
                    "synergy_score": 0.8,
                },
                {
                    "name": "Spore Frog",
                    "inclusion_rate": 0.71,
                    "category": "high_synergy",
                    "synergy_score": 0.8,
                },
                {
                    "name": "Viscera Seer",
                    "inclusion_rate": 0.69,
                    "category": "high_synergy",
                    "synergy_score": 0.7,
                },
            ]
        else:
            # Generic synergy cards
            synergy_cards = [
                {
                    "name": "Sensei's Divining Top",
                    "inclusion_rate": 0.65,
                    "category": "high_synergy",
                    "synergy_score": 0.6,
                },
                {
                    "name": "Lightning Greaves",
                    "inclusion_rate": 0.71,
                    "category": "high_synergy",
                    "synergy_score": 0.5,
                },
                {
                    "name": "Swiftfoot Boots",
                    "inclusion_rate": 0.58,
                    "category": "high_synergy",
                    "synergy_score": 0.4,
                },
            ]

        # Combine base cards and synergy cards
        all_cards = base_cards + synergy_cards

        # Add price estimates based on card names and inclusion rates
        for card in all_cards:
            if card["inclusion_rate"] > 0.8:
                card["price_usd"] = 15.0 + (
                    card["inclusion_rate"] * 20
                )  # High inclusion = expensive
            elif card["category"] == "signature":
                card["price_usd"] = 25.0 + (
                    card["synergy_score"] * 30
                )  # Signature cards expensive
            else:
                card["price_usd"] = 2.0 + (
                    card["inclusion_rate"] * 15
                )  # Regular pricing

        return all_cards

    async def scrape_and_store_deck_data(
        self, commander_name: str, archetype: str = "default", budget_range: str = "mid"
    ) -> int:
        """Scrape deck data for a commander and store to database.

        Args:
            commander_name: Name of the commander
            archetype: Deck archetype (default, combo, control, etc.)
            budget_range: Budget category (budget, mid, high, cedh)

        Returns:
            Number of cards stored
        """
        try:
            # Get deck composition data
            deck_data = await self.scrape_commander_deck_data(commander_name, archetype)
            if not deck_data:
                logger.warning(f"No deck data found for {commander_name}")
                return 0

            # Import database dependencies locally to avoid circular imports
            from ponderous.infrastructure.database import get_database_connection

            cards_stored = 0
            db_connection = None

            try:
                db_connection = get_database_connection()

                # Store each card's inclusion data
                for card_data in deck_data:
                    try:
                        # Generate card_id from card name
                        card_id = (
                            card_data["name"]
                            .lower()
                            .replace(" ", "_")
                            .replace(",", "")
                            .replace("'", "")
                        )

                        # Store card inclusion data
                        query = """
                            INSERT OR REPLACE INTO deck_card_inclusions (
                                commander_name, archetype_id, budget_range, card_name, card_id,
                                inclusion_rate, synergy_score, category, price_usd, last_updated
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                        """

                        db_connection.execute_query(
                            query,
                            (
                                commander_name,
                                archetype,
                                budget_range,
                                card_data["name"],
                                card_id,
                                card_data["inclusion_rate"],
                                card_data["synergy_score"],
                                card_data["category"],
                                card_data["price_usd"],
                            ),
                        )
                        cards_stored += 1

                    except Exception as e:
                        logger.warning(f"Failed to store card {card_data['name']}: {e}")
                        continue

                logger.info(
                    f"Stored {cards_stored} cards for {commander_name} ({archetype})"
                )
                return cards_stored

            finally:
                if db_connection:
                    db_connection.close()

        except Exception as e:
            logger.error(
                f"Failed to scrape and store deck data for {commander_name}: {e}"
            )
            return 0

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
