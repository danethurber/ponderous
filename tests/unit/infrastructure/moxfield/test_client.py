"""Tests for Moxfield API client."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import httpx
import pytest

from ponderous.infrastructure.moxfield import MoxfieldClient
from ponderous.infrastructure.moxfield.exceptions import (
    MoxfieldAPIError,
    MoxfieldAuthError,
    MoxfieldNotFoundError,
    MoxfieldRateLimitError,
    MoxfieldValidationError,
)
from ponderous.shared.config import MoxfieldConfig


class TestMoxfieldClient:
    """Test suite for MoxfieldClient."""

    @pytest.fixture
    def config(self) -> MoxfieldConfig:
        """Create test config."""
        return MoxfieldConfig(
            base_url="https://api.test.moxfield.com/v2",
            timeout=10.0,
            rate_limit=5.0,  # Higher rate limit for faster tests
        )

    @pytest.fixture
    def client(self, config: MoxfieldConfig) -> MoxfieldClient:
        """Create test client."""
        return MoxfieldClient(config)

    @pytest.fixture
    def mock_response(self) -> Mock:
        """Create mock HTTP response."""
        response = Mock(spec=httpx.Response)
        response.is_success = True
        response.status_code = 200
        response.json.return_value = {"test": "data"}
        return response

    def test_client_initialization(self, config: MoxfieldConfig) -> None:
        """Test client initialization with config."""
        client = MoxfieldClient(config)

        assert client.config == config
        assert client.base_url == "https://api.test.moxfield.com/v2"
        assert client.rate_limiter.max_requests_per_second == 5.0
        assert client.client.timeout.timeout == 10.0

    def test_client_initialization_default_config(self) -> None:
        """Test client initialization with default config."""
        client = MoxfieldClient()

        assert client.config is not None
        assert client.base_url == "https://api2.moxfield.com/v2"
        assert client.rate_limiter.max_requests_per_second == 2.0

    @pytest.mark.asyncio
    async def test_rate_limiting(self, client: MoxfieldClient) -> None:
        """Test that rate limiting works correctly."""
        rate_limiter = client.rate_limiter

        # First request should be immediate
        start_time = asyncio.get_event_loop().time()
        await rate_limiter.acquire()
        first_time = asyncio.get_event_loop().time() - start_time

        # Second request should be delayed by rate limit
        start_time = asyncio.get_event_loop().time()
        await rate_limiter.acquire()
        second_time = asyncio.get_event_loop().time() - start_time

        # Should have been delayed by approximately 1/rate_limit seconds
        expected_delay = 1.0 / rate_limiter.max_requests_per_second
        assert first_time < 0.01  # First request immediate
        assert second_time >= expected_delay * 0.9  # Allow some variance

    def test_handle_http_error_401(self, client: MoxfieldClient) -> None:
        """Test handling of 401 authentication errors."""
        response = Mock(spec=httpx.Response)
        response.status_code = 401
        response.json.return_value = {"message": "Unauthorized"}
        response.text = "Unauthorized"

        with pytest.raises(MoxfieldAuthError) as exc_info:
            client._handle_http_error(response)

        assert "Unauthorized" in str(exc_info.value)

    def test_handle_http_error_404(self, client: MoxfieldClient) -> None:
        """Test handling of 404 not found errors."""
        response = Mock(spec=httpx.Response)
        response.status_code = 404
        response.json.return_value = {"message": "User not found"}
        response.text = "User not found"

        with pytest.raises(MoxfieldNotFoundError) as exc_info:
            client._handle_http_error(response)

        assert "User not found" in str(exc_info.value)

    def test_handle_http_error_429(self, client: MoxfieldClient) -> None:
        """Test handling of 429 rate limit errors."""
        response = Mock(spec=httpx.Response)
        response.status_code = 429
        response.json.return_value = {"message": "Rate limit exceeded"}
        response.text = "Rate limit exceeded"
        response.headers = {"Retry-After": "60"}

        with pytest.raises(MoxfieldRateLimitError) as exc_info:
            client._handle_http_error(response)

        assert exc_info.value.retry_after == 60
        assert "Rate limit exceeded" in str(exc_info.value)

    def test_handle_http_error_400(self, client: MoxfieldClient) -> None:
        """Test handling of 400 validation errors."""
        response = Mock(spec=httpx.Response)
        response.status_code = 400
        response.json.return_value = {"message": "Invalid request"}
        response.text = "Invalid request"

        with pytest.raises(MoxfieldValidationError) as exc_info:
            client._handle_http_error(response)

        assert "Invalid request" in str(exc_info.value)

    def test_handle_http_error_500(self, client: MoxfieldClient) -> None:
        """Test handling of 500 server errors."""
        response = Mock(spec=httpx.Response)
        response.status_code = 500
        response.json.return_value = {"message": "Internal server error"}
        response.text = "Internal server error"

        with pytest.raises(MoxfieldAPIError) as exc_info:
            client._handle_http_error(response)

        assert exc_info.value.status_code == 500
        assert "Internal server error" in str(exc_info.value)

    def test_handle_http_error_json_decode_failure(
        self, client: MoxfieldClient
    ) -> None:
        """Test handling when JSON decode fails."""
        response = Mock(spec=httpx.Response)
        response.status_code = 500
        response.json.side_effect = ValueError("Invalid JSON")
        response.text = "Server Error"

        with pytest.raises(MoxfieldAPIError) as exc_info:
            client._handle_http_error(response)

        assert "Server Error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_success(
        self, client: MoxfieldClient, mock_response: Mock
    ) -> None:
        """Test successful request making."""
        with patch.object(
            client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            response = await client._make_request("GET", "/test/endpoint")

            assert response == mock_response
            mock_request.assert_called_once_with(
                "GET", "https://api.test.moxfield.com/v2/test/endpoint"
            )

    @pytest.mark.asyncio
    async def test_make_request_http_error(self, client: MoxfieldClient) -> None:
        """Test request making with HTTP error."""
        with patch.object(
            client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.side_effect = httpx.HTTPError("Connection failed")

            with pytest.raises(MoxfieldAPIError) as exc_info:
                await client._make_request("GET", "/test/endpoint")

            assert "Network error" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_make_request_retries_on_connection_error(
        self, client: MoxfieldClient, mock_response: Mock
    ) -> None:
        """Test that connection errors trigger retries."""
        with patch.object(
            client.client, "request", new_callable=AsyncMock
        ) as mock_request:
            # First two calls fail, third succeeds
            mock_request.side_effect = [
                httpx.ConnectError("Connection failed"),
                httpx.ConnectError("Connection failed"),
                mock_response,
            ]

            response = await client._make_request("GET", "/test/endpoint")

            assert response == mock_response
            assert mock_request.call_count == 3

    @pytest.mark.asyncio
    async def test_get_user_profile_success(self, client: MoxfieldClient) -> None:
        """Test successful user profile retrieval."""
        profile_data = {
            "username": "testuser",
            "display_name": "Test User",
            "public_profile": True,
            "collection_count": 1000,
            "deck_count": 5,
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.json.return_value = profile_data

        with patch.object(
            client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            profile = await client.get_user_profile("testuser")

            assert profile.username == "testuser"
            assert profile.display_name == "Test User"
            assert profile.public_profile is True
            assert profile.collection_count == 1000
            assert profile.deck_count == 5

            mock_request.assert_called_once_with("GET", "users/testuser")

    @pytest.mark.asyncio
    async def test_get_user_profile_invalid_data(self, client: MoxfieldClient) -> None:
        """Test user profile with invalid data."""
        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.json.return_value = {"invalid": "data"}

        with patch.object(
            client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            with pytest.raises(MoxfieldValidationError) as exc_info:
                await client.get_user_profile("testuser")

            assert "Invalid user profile data" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_user_profile_empty_username(
        self, client: MoxfieldClient
    ) -> None:
        """Test user profile with empty username."""
        with pytest.raises(MoxfieldValidationError) as exc_info:
            await client.get_user_profile("")

        assert "Username cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_collection_success(self, client: MoxfieldClient) -> None:
        """Test successful collection retrieval."""
        collection_data = {
            "card1": {
                "id": "card1",
                "name": "Lightning Bolt",
                "quantity": 4,
                "foilQuantity": 1,
                "priceUsd": 2.50,
            },
            "card2": {
                "id": "card2",
                "name": "Counterspell",
                "quantity": 2,
                "foilQuantity": 0,
                "priceUsd": 1.00,
            },
        }

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.json.return_value = collection_data

        with patch.object(
            client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            collection = await client.get_collection("testuser")

            assert collection.username == "testuser"
            assert collection.unique_cards == 2
            assert collection.total_cards == 7  # 4+1+2+0
            assert len(collection.collection) == 2

            # Check specific cards
            assert "card1" in collection.collection
            assert collection.collection["card1"].name == "Lightning Bolt"
            assert collection.collection["card1"].total_quantity == 5

            mock_request.assert_called_once_with("GET", "users/testuser/collection")

    @pytest.mark.asyncio
    async def test_get_collection_empty_username(self, client: MoxfieldClient) -> None:
        """Test collection retrieval with empty username."""
        with pytest.raises(MoxfieldValidationError) as exc_info:
            await client.get_collection("")

        assert "Username cannot be empty" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_public_decks_success(self, client: MoxfieldClient) -> None:
        """Test successful public decks retrieval."""
        decks_data = [
            {
                "id": "deck1",
                "name": "Test Deck 1",
                "format": "commander",
                "public": True,
                "commanders": [],
                "mainboard": {},
                "card_count": 100,
            },
            {
                "id": "deck2",
                "name": "Test Deck 2",
                "format": "commander",
                "public": True,
                "commanders": [],
                "mainboard": {},
                "card_count": 99,
            },
        ]

        mock_response = Mock(spec=httpx.Response)
        mock_response.is_success = True
        mock_response.json.return_value = decks_data

        with patch.object(
            client, "_make_request", new_callable=AsyncMock
        ) as mock_request:
            mock_request.return_value = mock_response

            decks = await client.get_public_decks("testuser", limit=10)

            assert len(decks) == 2
            assert decks[0].id == "deck1"
            assert decks[0].name == "Test Deck 1"
            assert decks[0].format == "commander"
            assert decks[1].id == "deck2"
            assert decks[1].name == "Test Deck 2"

            mock_request.assert_called_once_with(
                "GET", "users/testuser/decks", params={"limit": 10, "public": "true"}
            )

    @pytest.mark.asyncio
    async def test_get_public_decks_invalid_limit(self, client: MoxfieldClient) -> None:
        """Test public decks with invalid limit."""
        with pytest.raises(MoxfieldValidationError) as exc_info:
            await client.get_public_decks("testuser", limit=0)

        assert "Limit must be positive" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_verify_username_exists(self, client: MoxfieldClient) -> None:
        """Test username verification for existing user."""
        with patch.object(
            client, "get_user_profile", new_callable=AsyncMock
        ) as mock_profile:
            mock_profile.return_value = Mock()

            result = await client.verify_username("testuser")

            assert result is True
            mock_profile.assert_called_once_with("testuser")

    @pytest.mark.asyncio
    async def test_verify_username_not_found(self, client: MoxfieldClient) -> None:
        """Test username verification for non-existent user."""
        with patch.object(
            client, "get_user_profile", new_callable=AsyncMock
        ) as mock_profile:
            mock_profile.side_effect = MoxfieldNotFoundError("User not found")

            result = await client.verify_username("nonexistent")

            assert result is False

    @pytest.mark.asyncio
    async def test_verify_username_api_error(self, client: MoxfieldClient) -> None:
        """Test username verification with API error."""
        with patch.object(
            client, "get_user_profile", new_callable=AsyncMock
        ) as mock_profile:
            mock_profile.side_effect = MoxfieldAPIError("Server error")

            result = await client.verify_username("testuser")

            # Should assume username exists for other API errors
            assert result is True

    @pytest.mark.asyncio
    async def test_context_manager(self, config: MoxfieldConfig) -> None:
        """Test client as async context manager."""
        async with MoxfieldClient(config) as client:
            assert isinstance(client, MoxfieldClient)
            assert client.client is not None

        # Client should be closed after context exit
        assert client.client.is_closed

    @pytest.mark.asyncio
    async def test_close(self, client: MoxfieldClient) -> None:
        """Test explicit client closure."""
        assert not client.client.is_closed

        await client.close()

        assert client.client.is_closed
