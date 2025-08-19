"""Moxfield API client with rate limiting and error handling."""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ponderous.shared.config import MoxfieldConfig

from .exceptions import (
    MoxfieldAPIError,
    MoxfieldAuthError,
    MoxfieldNotFoundError,
    MoxfieldRateLimitError,
    MoxfieldValidationError,
)
from .models import CollectionResponse, DeckResponse, UserProfile

logger = logging.getLogger(__name__)


class RateLimiter:
    """Simple rate limiter for API requests."""

    def __init__(self, max_requests_per_second: float) -> None:
        self.max_requests_per_second = max_requests_per_second
        self.min_interval = 1.0 / max_requests_per_second
        self.last_request_time = 0.0

    async def acquire(self) -> None:
        """Wait if necessary to respect rate limit."""
        now = asyncio.get_event_loop().time()
        time_since_last = now - self.last_request_time

        if time_since_last < self.min_interval:
            wait_time = self.min_interval - time_since_last
            logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
            await asyncio.sleep(wait_time)

        self.last_request_time = asyncio.get_event_loop().time()


class MoxfieldClient:
    """Professional Moxfield API client with rate limiting and error handling."""

    def __init__(self, config: MoxfieldConfig | None = None) -> None:
        """Initialize the Moxfield client.

        Args:
            config: Moxfield configuration. If None, uses default settings.
        """
        self.config = config or MoxfieldConfig()
        self.rate_limiter = RateLimiter(self.config.rate_limit)
        self.base_url = self.config.base_url.rstrip("/")

        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(self.config.timeout),
            headers={
                "User-Agent": "Ponderous/1.0.0 (MTG Collection Analyzer)",
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            follow_redirects=True,
        )

        logger.info(f"Initialized Moxfield client with base URL: {self.base_url}")

    async def __aenter__(self) -> "MoxfieldClient":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def close(self) -> None:
        """Close the HTTP client."""
        await self.client.aclose()

    def _handle_http_error(self, response: httpx.Response) -> None:
        """Handle HTTP errors and convert to appropriate exceptions."""
        status_code = response.status_code

        try:
            error_data = response.json()
            message = error_data.get("message", response.text)
        except Exception:
            message = response.text or f"HTTP {status_code}"

        if status_code == 401:
            raise MoxfieldAuthError(message)
        elif status_code == 404:
            raise MoxfieldNotFoundError(message)
        elif status_code == 429:
            retry_after = response.headers.get("Retry-After")
            retry_seconds = int(retry_after) if retry_after else None
            raise MoxfieldRateLimitError(message, retry_seconds)
        elif 400 <= status_code < 500:
            raise MoxfieldValidationError(message)
        else:
            raise MoxfieldAPIError(message, status_code)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    async def _make_request(
        self,
        method: str,
        endpoint: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """Make HTTP request with rate limiting and error handling."""
        await self.rate_limiter.acquire()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        logger.debug(f"Making {method} request to {url}")

        try:
            response = await self.client.request(method, url, **kwargs)

            if not response.is_success:
                self._handle_http_error(response)

            return response

        except (httpx.ConnectError, httpx.TimeoutException):
            # Let these bubble up for tenacity to retry
            raise
        except httpx.HTTPError as e:
            logger.error(f"HTTP error for {url}: {e}")
            raise MoxfieldAPIError(f"Network error: {e}") from e

    async def get_user_profile(self, username: str) -> UserProfile:
        """Get user profile information.

        Args:
            username: Moxfield username

        Returns:
            User profile data

        Raises:
            MoxfieldAPIError: If the request fails
            MoxfieldNotFoundError: If the user is not found
        """
        if not username.strip():
            raise MoxfieldValidationError("Username cannot be empty")

        endpoint = f"users/{username.strip()}"
        response = await self._make_request("GET", endpoint)

        try:
            data = response.json()
            return UserProfile(**data)
        except Exception as e:
            logger.error(f"Failed to parse user profile response: {e}")
            raise MoxfieldValidationError(f"Invalid user profile data: {e}") from e

    async def get_collection(self, username: str) -> CollectionResponse:
        """Get user's collection data.

        Args:
            username: Moxfield username

        Returns:
            Collection data with all cards

        Raises:
            MoxfieldAPIError: If the request fails
            MoxfieldNotFoundError: If the user or collection is not found
        """
        if not username.strip():
            raise MoxfieldValidationError("Username cannot be empty")

        endpoint = f"users/{username.strip()}/collection"
        response = await self._make_request("GET", endpoint)

        try:
            data = response.json()

            collection_data = {
                "username": username,
                "collection": data,
                "lastUpdated": datetime.now(UTC),
            }

            collection_response = CollectionResponse(**collection_data)

            # Calculate totals
            total_cards, unique_cards = collection_response.calculate_totals()
            collection_response.total_cards = total_cards
            collection_response.unique_cards = unique_cards

            logger.info(
                f"Retrieved collection for {username}: {unique_cards} unique cards, {total_cards} total"
            )
            return collection_response

        except Exception as e:
            logger.error(f"Failed to parse collection response: {e}")
            raise MoxfieldValidationError(f"Invalid collection data: {e}") from e

    async def get_public_decks(
        self, username: str, limit: int = 50
    ) -> list[DeckResponse]:
        """Get user's public decks.

        Args:
            username: Moxfield username
            limit: Maximum number of decks to return

        Returns:
            List of public decks

        Raises:
            MoxfieldAPIError: If the request fails
            MoxfieldNotFoundError: If the user is not found
        """
        if not username.strip():
            raise MoxfieldValidationError("Username cannot be empty")
        if limit <= 0:
            raise MoxfieldValidationError("Limit must be positive")

        endpoint = f"users/{username.strip()}/decks"
        params = {"limit": limit, "public": "true"}

        response = await self._make_request("GET", endpoint, params=params)

        try:
            data = response.json()
            decks = []

            # Handle different response formats
            deck_list = data if isinstance(data, list) else data.get("decks", [])

            for deck_data in deck_list:
                decks.append(DeckResponse(**deck_data))

            logger.info(f"Retrieved {len(decks)} public decks for {username}")
            return decks

        except Exception as e:
            logger.error(f"Failed to parse decks response: {e}")
            raise MoxfieldValidationError(f"Invalid decks data: {e}") from e

    async def get_deck_details(self, deck_id: str) -> DeckResponse:
        """Get detailed information about a specific deck.

        Args:
            deck_id: Moxfield deck ID

        Returns:
            Detailed deck information

        Raises:
            MoxfieldAPIError: If the request fails
            MoxfieldNotFoundError: If the deck is not found
        """
        if not deck_id.strip():
            raise MoxfieldValidationError("Deck ID cannot be empty")

        endpoint = f"decks/all/{deck_id.strip()}"
        response = await self._make_request("GET", endpoint)

        try:
            data = response.json()
            return DeckResponse(**data)
        except Exception as e:
            logger.error(f"Failed to parse deck details response: {e}")
            raise MoxfieldValidationError(f"Invalid deck data: {e}") from e

    async def verify_username(self, username: str) -> bool:
        """Verify that a username exists and has a public profile.

        Args:
            username: Username to verify

        Returns:
            True if username exists and is accessible, False otherwise
        """
        try:
            await self.get_user_profile(username)
            return True
        except MoxfieldNotFoundError:
            return False
        except MoxfieldAPIError:
            # Other API errors might be temporary, so we assume username exists
            return True
