"""Tests for Moxfield dlt data source."""

from collections.abc import AsyncGenerator, AsyncIterator
from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from ponderous.infrastructure.etl.moxfield_source import (
    moxfield_collection_items,
    moxfield_collection_source,
    moxfield_user_profile_source,
)
from ponderous.infrastructure.moxfield.exceptions import (
    MoxfieldAPIError,
    MoxfieldNotFoundError,
)
from ponderous.infrastructure.moxfield.models import (
    CollectionResponse,
    UserProfile,
)
from ponderous.shared.config import MoxfieldConfig


class TestMoxfieldUserProfileSource:
    """Test suite for moxfield_user_profile_source."""

    @pytest.fixture
    def mock_profile(self) -> UserProfile:
        """Create mock user profile."""
        return UserProfile(
            username="testuser",
            display_name="Test User",
            public_profile=True,
            collection_count=1000,
            deck_count=5,
        )

    @pytest.fixture
    def mock_config(self) -> MoxfieldConfig:
        """Create mock Moxfield config."""
        return MoxfieldConfig(
            base_url="https://api.test.moxfield.com/v2",
            timeout=10.0,
            rate_limit=5.0,
        )

    @pytest.mark.asyncio
    async def test_user_profile_source_success(
        self, mock_profile: UserProfile, mock_config: MoxfieldConfig
    ) -> None:
        """Test successful user profile source execution."""
        with patch(
            "ponderous.infrastructure.etl.moxfield_source.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.get_user_profile.return_value = mock_profile

            # Execute the source
            source = moxfield_user_profile_source("testuser", config=mock_config)

            # Get the data - dlt sources are generators
            items = []
            async for item in source:
                items.append(item)

            # Verify results
            assert len(items) == 1
            profile_data = items[0]

            assert profile_data["username"] == "testuser"
            assert profile_data["display_name"] == "Test User"
            assert profile_data["public_profile"] is True
            assert profile_data["collection_count"] == 1000
            assert profile_data["deck_count"] == 5
            assert "extracted_at" in profile_data
            assert isinstance(profile_data["extracted_at"], datetime)

            # Verify client was called correctly
            mock_client.get_user_profile.assert_called_once_with("testuser")

    @pytest.mark.asyncio
    async def test_user_profile_source_not_found(
        self, mock_config: MoxfieldConfig
    ) -> None:
        """Test user profile source with user not found."""
        with patch(
            "ponderous.infrastructure.etl.moxfield_source.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client to raise not found error
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.get_user_profile.side_effect = MoxfieldNotFoundError(
                "User not found"
            )

            # Execute the source
            source = moxfield_user_profile_source("nonexistent", config=mock_config)

            # Should raise the exception
            with pytest.raises(MoxfieldNotFoundError):
                items = []
                async for item in source:
                    items.append(item)

    @pytest.mark.asyncio
    async def test_user_profile_source_api_error(
        self, mock_config: MoxfieldConfig
    ) -> None:
        """Test user profile source with API error."""
        with patch(
            "ponderous.infrastructure.etl.moxfield_source.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client to raise API error
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.get_user_profile.side_effect = MoxfieldAPIError("Server error")

            # Execute the source
            source = moxfield_user_profile_source("testuser", config=mock_config)

            # Should raise the exception
            with pytest.raises(MoxfieldAPIError):
                items = []
                async for item in source:
                    items.append(item)

    @pytest.mark.asyncio
    async def test_user_profile_source_empty_username(self) -> None:
        """Test user profile source with empty username."""
        # Should raise ValueError for empty username
        with pytest.raises(ValueError, match="Username cannot be empty"):
            source = moxfield_user_profile_source("")
            # Try to consume the generator
            items = []
            async for item in source:
                items.append(item)


class TestMoxfieldCollectionItems:
    """Test suite for moxfield_collection_items resource."""

    @pytest.fixture
    def mock_collection_data(self) -> dict[str, dict[str, Any]]:
        """Create mock collection data."""
        return {
            "card1": {
                "id": "scryfall_id_1",
                "name": "Lightning Bolt",
                "quantity": 4,
                "foilQuantity": 1,
                "priceUsd": 2.50,
                "set": "M21",
                "rarity": "common",
                "colors": ["R"],
                "type": "Instant",
            },
            "card2": {
                "id": "scryfall_id_2",
                "name": "Counterspell",
                "quantity": 2,
                "foilQuantity": 0,
                "priceUsd": 1.00,
                "set": "M21",
                "rarity": "common",
                "colors": ["U"],
                "type": "Instant",
            },
        }

    @pytest.fixture
    def mock_collection_response(
        self, mock_collection_data: dict[str, dict[str, Any]]
    ) -> CollectionResponse:
        """Create mock collection response."""
        return CollectionResponse(
            username="testuser",
            collection=mock_collection_data,
        )

    @pytest.mark.asyncio
    async def test_collection_items_success(
        self, mock_collection_response: CollectionResponse
    ) -> None:
        """Test successful collection items extraction."""
        with patch(
            "ponderous.infrastructure.etl.moxfield_source.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.get_collection.return_value = mock_collection_response

            # Execute the resource
            resource = moxfield_collection_items("testuser")

            # Get the data
            items = []
            async for item in resource:
                items.append(item)

            # Verify results
            assert len(items) == 2

            # Check first card
            card1 = items[0]
            assert card1["card_id"] == "scryfall_id_1"
            assert card1["name"] == "Lightning Bolt"
            assert card1["quantity"] == 4
            assert card1["foil_quantity"] == 1
            assert card1["price_usd"] == 2.50
            assert card1["total_quantity"] == 5
            assert card1["total_value"] == 12.50  # (4 * 2.50) + (1 * 2.50)
            assert card1["username"] == "testuser"
            assert "extracted_at" in card1

            # Check second card
            card2 = items[1]
            assert card2["card_id"] == "scryfall_id_2"
            assert card2["name"] == "Counterspell"
            assert card2["quantity"] == 2
            assert card2["foil_quantity"] == 0
            assert card2["total_quantity"] == 2
            assert card2["total_value"] == 2.00

    @pytest.mark.asyncio
    async def test_collection_items_empty_collection(self) -> None:
        """Test collection items with empty collection."""
        empty_response = CollectionResponse(
            username="testuser",
            collection={},
        )

        with patch(
            "ponderous.infrastructure.etl.moxfield_source.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.get_collection.return_value = empty_response

            # Execute the resource
            resource = moxfield_collection_items("testuser")

            # Get the data
            items = []
            async for item in resource:
                items.append(item)

            # Should have no items
            assert len(items) == 0

    @pytest.mark.asyncio
    async def test_collection_items_api_error(self) -> None:
        """Test collection items with API error."""
        with patch(
            "ponderous.infrastructure.etl.moxfield_source.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client to raise error
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.get_collection.side_effect = MoxfieldAPIError("Server error")

            # Execute the resource
            resource = moxfield_collection_items("testuser")

            # Should raise the exception
            with pytest.raises(MoxfieldAPIError):
                items = []
                async for item in resource:
                    items.append(item)

    @pytest.mark.asyncio
    async def test_collection_items_data_transformation(self) -> None:
        """Test proper data transformation in collection items."""
        collection_data = {
            "test_card": {
                "id": "test_scryfall_id",
                "name": "Test Card",
                "quantity": 3,
                "foilQuantity": 2,
                "priceUsd": 5.75,
                "priceUsdFoil": 12.25,
                "set": "TEST",
                "rarity": "rare",
                "cmc": 4,
                "colors": ["W", "U"],
                "type": "Creature — Human Wizard",
                "text": "Test oracle text.",
            }
        }

        collection_response = CollectionResponse(
            username="testuser",
            collection=collection_data,
        )

        with patch(
            "ponderous.infrastructure.etl.moxfield_source.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.get_collection.return_value = collection_response

            # Execute the resource
            resource = moxfield_collection_items("testuser")

            # Get the data
            items = []
            async for item in resource:
                items.append(item)

            # Verify transformation
            assert len(items) == 1
            card = items[0]

            assert card["card_id"] == "test_scryfall_id"
            assert card["name"] == "Test Card"
            assert card["quantity"] == 3
            assert card["foil_quantity"] == 2
            assert card["price_usd"] == 5.75
            assert card["price_usd_foil"] == 12.25
            assert card["total_quantity"] == 5
            assert card["total_value"] == 41.75  # (3 * 5.75) + (2 * 12.25)
            assert card["set_code"] == "TEST"
            assert card["rarity"] == "rare"
            assert card["mana_cost"] == 4
            assert card["color_identity"] == ["W", "U"]
            assert card["type_line"] == "Creature — Human Wizard"
            assert card["oracle_text"] == "Test oracle text."
            assert card["username"] == "testuser"
            assert isinstance(card["extracted_at"], datetime)


class TestMoxfieldCollectionSource:
    """Test suite for moxfield_collection_source."""

    @pytest.fixture
    def mock_config(self) -> MoxfieldConfig:
        """Create mock Moxfield config."""
        return MoxfieldConfig(
            base_url="https://api.test.moxfield.com/v2",
            timeout=10.0,
            rate_limit=5.0,
        )

    @pytest.mark.asyncio
    async def test_collection_source_success(self, mock_config: MoxfieldConfig) -> None:
        """Test successful collection source execution."""
        # Mock the individual resources
        with (
            patch(
                "ponderous.infrastructure.etl.moxfield_source.moxfield_user_profile_source"
            ) as mock_profile_source,
            patch(
                "ponderous.infrastructure.etl.moxfield_source.moxfield_collection_items"
            ) as mock_items_resource,
        ):
            # Setup mock profile source
            async def mock_profile_gen() -> AsyncGenerator[dict[str, Any], None]:
                yield {
                    "username": "testuser",
                    "display_name": "Test User",
                    "extracted_at": datetime.now(UTC),
                }

            mock_profile_source.return_value = mock_profile_gen()

            # Setup mock collection items
            async def mock_items_gen() -> AsyncGenerator[dict[str, Any], None]:
                yield {
                    "card_id": "card1",
                    "name": "Lightning Bolt",
                    "username": "testuser",
                    "extracted_at": datetime.now(UTC),
                }
                yield {
                    "card_id": "card2",
                    "name": "Counterspell",
                    "username": "testuser",
                    "extracted_at": datetime.now(UTC),
                }

            mock_items_resource.return_value = mock_items_gen()

            # Execute the source
            source = moxfield_collection_source("testuser", config=mock_config)

            # The source should be a dlt source object
            assert hasattr(source, "resources")
            assert hasattr(source, "name")
            assert source.name == "moxfield_collection"

            # Verify the resources were called with correct parameters
            mock_profile_source.assert_called_once_with("testuser", config=mock_config)
            mock_items_resource.assert_called_once_with("testuser", config=mock_config)

    @pytest.mark.asyncio
    async def test_collection_source_default_config(self) -> None:
        """Test collection source with default config."""
        with (
            patch(
                "ponderous.infrastructure.etl.moxfield_source.moxfield_user_profile_source"
            ) as mock_profile_source,
            patch(
                "ponderous.infrastructure.etl.moxfield_source.moxfield_collection_items"
            ) as mock_items_resource,
        ):
            # Setup minimal mock returns
            async def mock_empty_gen() -> AsyncGenerator[dict[str, Any], None]:
                return
                yield  # Make it a generator but yield nothing

            mock_profile_source.return_value = mock_empty_gen()
            mock_items_resource.return_value = mock_empty_gen()

            # Execute the source without config
            moxfield_collection_source("testuser")

            # Verify the resources were called with default config
            mock_profile_source.assert_called_once_with("testuser", config=None)
            mock_items_resource.assert_called_once_with("testuser", config=None)

    def test_collection_source_empty_username(self) -> None:
        """Test collection source with empty username."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            moxfield_collection_source("")

    def test_collection_source_none_username(self) -> None:
        """Test collection source with None username."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            moxfield_collection_source(None)


class TestAsyncGeneratorHelpers:
    """Test async generator helper functionality."""

    @pytest.mark.asyncio
    async def test_async_generator_consumption(self) -> None:
        """Test that async generators work correctly with dlt."""

        async def test_generator() -> AsyncIterator[dict[str, Any]]:
            """Test async generator."""
            for i in range(3):
                yield {"item": i, "timestamp": datetime.now(UTC)}

        # Test that we can consume the generator
        items = []
        async for item in test_generator():
            items.append(item)

        assert len(items) == 3
        assert items[0]["item"] == 0
        assert items[1]["item"] == 1
        assert items[2]["item"] == 2

        # Verify all items have timestamps
        for item in items:
            assert "timestamp" in item
            assert isinstance(item["timestamp"], datetime)

    @pytest.mark.asyncio
    async def test_error_handling_in_generators(self) -> None:
        """Test error handling within async generators."""

        async def failing_generator() -> AsyncIterator[dict[str, Any]]:
            """Generator that fails after yielding one item."""
            yield {"item": "first"}
            raise ValueError("Test error")

        # Should get the first item, then raise the error
        items = []
        with pytest.raises(ValueError, match="Test error"):
            async for item in failing_generator():
                items.append(item)

        # Should have gotten the first item before the error
        assert len(items) == 1
        assert items[0]["item"] == "first"


class TestIntegrationWithDlt:
    """Integration tests with dlt framework."""

    @pytest.mark.asyncio
    async def test_dlt_source_metadata(self) -> None:
        """Test that dlt source has correct metadata."""
        source = moxfield_collection_source("testuser")

        # Check source metadata
        assert source.name == "moxfield_collection"
        assert hasattr(source, "resources")

        # Check that we have the expected resources
        resource_names = [r.name for r in source.resources.values()]
        assert "user_profile" in resource_names
        assert "collection_items" in resource_names

    @pytest.mark.asyncio
    async def test_resource_configuration(self) -> None:
        """Test that resources are configured correctly."""
        with (
            patch(
                "ponderous.infrastructure.etl.moxfield_source.moxfield_user_profile_source"
            ) as mock_profile,
            patch(
                "ponderous.infrastructure.etl.moxfield_source.moxfield_collection_items"
            ) as mock_items,
        ):
            # Setup mock returns
            async def mock_gen() -> AsyncGenerator[dict[str, Any], None]:
                return
                yield  # Make generator but yield nothing

            mock_profile.return_value = mock_gen()
            mock_items.return_value = mock_gen()

            # Create source
            source = moxfield_collection_source("testuser")

            # Verify resources exist and have correct names
            assert "user_profile" in source.resources
            assert "collection_items" in source.resources

            # Resources should be callable
            profile_resource = source.resources["user_profile"]
            items_resource = source.resources["collection_items"]

            assert callable(profile_resource)
            assert callable(items_resource)
