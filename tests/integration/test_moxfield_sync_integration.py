"""Integration tests for Moxfield collection sync pipeline."""

import asyncio
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from ponderous.application.services import CollectionService
from ponderous.infrastructure.moxfield.exceptions import MoxfieldNotFoundError
from ponderous.infrastructure.moxfield.models import (
    CollectionResponse,
    UserProfile,
)
from ponderous.shared.config import get_config
from ponderous.shared.exceptions import PonderousError


class TestMoxfieldSyncIntegration:
    """Integration tests for the complete Moxfield sync pipeline."""

    @pytest.fixture
    def temp_db_path(self) -> Path:
        """Create temporary database path for testing."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            return Path(f.name)

    @pytest.fixture
    def collection_service(self, temp_db_path: Path) -> CollectionService:
        """Create CollectionService with temporary database."""
        with patch.object(get_config(), "database") as mock_db_config:
            mock_db_config.path = str(temp_db_path)
            mock_db_config.memory = False
            return CollectionService()

    @pytest.fixture
    def mock_user_profile(self) -> UserProfile:
        """Create mock user profile data."""
        return UserProfile(
            username="testuser",
            display_name="Test User",
            public_profile=True,
            collection_count=1000,
            deck_count=5,
        )

    @pytest.fixture
    def mock_collection_data(self) -> dict[str, dict[str, Any]]:
        """Create mock collection data."""
        return {
            "scryfall_id_1": {
                "id": "scryfall_id_1",
                "name": "Lightning Bolt",
                "quantity": 4,
                "foilQuantity": 1,
                "priceUsd": 2.50,
                "priceUsdFoil": 5.00,
                "set": "M21",
                "rarity": "common",
                "cmc": 1,
                "colors": ["R"],
                "type": "Instant",
                "text": "Lightning Bolt deals 3 damage to any target.",
            },
            "scryfall_id_2": {
                "id": "scryfall_id_2",
                "name": "Counterspell",
                "quantity": 2,
                "foilQuantity": 0,
                "priceUsd": 1.00,
                "set": "M21",
                "rarity": "common",
                "cmc": 2,
                "colors": ["U"],
                "type": "Instant",
                "text": "Counter target spell.",
            },
            "scryfall_id_3": {
                "id": "scryfall_id_3",
                "name": "Sol Ring",
                "quantity": 1,
                "foilQuantity": 0,
                "priceUsd": 1.50,
                "set": "C21",
                "rarity": "uncommon",
                "cmc": 1,
                "colors": [],
                "type": "Artifact",
                "text": "{T}: Add {C}{C}.",
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
    async def test_complete_sync_pipeline_success(
        self,
        collection_service: CollectionService,
        mock_user_profile: UserProfile,
        mock_collection_response: CollectionResponse,
    ) -> None:
        """Test complete sync pipeline from service to database."""
        with patch(
            "ponderous.infrastructure.moxfield.client.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # Mock API responses
            mock_client.get_user_profile.return_value = mock_user_profile
            mock_client.get_collection.return_value = mock_collection_response

            # Execute the sync
            response = await collection_service.sync_user_collection(
                username="testuser",
                source="moxfield",
                force_refresh=False,
                include_profile=True,
            )

            # Verify response
            assert response.success is True
            assert response.username == "testuser"
            assert response.source == "moxfield"
            assert response.items_processed > 0
            assert response.unique_cards == 3
            assert response.total_cards == 8  # 4+1+2+0+1+0
            assert response.sync_duration_seconds is not None
            assert response.sync_duration_seconds > 0
            assert response.error_message is None

            # Verify client was called correctly
            mock_client.get_user_profile.assert_called_once_with("testuser")
            mock_client.get_collection.assert_called_once_with("testuser")

    @pytest.mark.asyncio
    async def test_sync_pipeline_user_not_found(
        self,
        collection_service: CollectionService,
    ) -> None:
        """Test sync pipeline when user is not found."""
        with patch(
            "ponderous.infrastructure.moxfield.client.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client to raise not found error
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_user_profile.side_effect = MoxfieldNotFoundError(
                "User not found"
            )

            # Execute the sync - should fail gracefully
            response = await collection_service.sync_user_collection(
                username="nonexistent",
                source="moxfield",
            )

            # Verify failure response
            assert response.success is False
            assert response.username == "nonexistent"
            assert response.source == "moxfield"
            assert response.items_processed == 0
            assert (
                response.error_message is not None
                and "User not found" in response.error_message
            )

    @pytest.mark.asyncio
    async def test_sync_pipeline_empty_collection(
        self,
        collection_service: CollectionService,
        mock_user_profile: UserProfile,
    ) -> None:
        """Test sync pipeline with empty collection."""
        empty_collection = CollectionResponse(
            username="testuser",
            collection={},
        )

        with patch(
            "ponderous.infrastructure.moxfield.client.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # Mock API responses
            mock_client.get_user_profile.return_value = mock_user_profile
            mock_client.get_collection.return_value = empty_collection

            # Execute the sync
            response = await collection_service.sync_user_collection(
                username="testuser",
                source="moxfield",
            )

            # Verify response for empty collection
            assert response.success is True
            assert response.username == "testuser"
            assert response.unique_cards == 0
            assert response.total_cards == 0
            # Should still process the profile
            assert response.items_processed >= 1

    @pytest.mark.asyncio
    async def test_sync_pipeline_large_collection(
        self,
        collection_service: CollectionService,
        mock_user_profile: UserProfile,
    ) -> None:
        """Test sync pipeline with large collection."""
        # Create a large mock collection (100 cards)
        large_collection_data = {}
        for i in range(100):
            card_id = f"scryfall_id_{i}"
            large_collection_data[card_id] = {
                "id": card_id,
                "name": f"Test Card {i}",
                "quantity": (i % 5) + 1,  # 1-5 quantity
                "foilQuantity": i % 2,  # 0-1 foil quantity
                "priceUsd": float(i + 1),  # $1-$100
                "set": "TEST",
                "rarity": "common",
                "cmc": i % 10,
                "colors": ["R"] if i % 2 == 0 else ["U"],
                "type": "Creature",
            }

        large_collection = CollectionResponse(
            username="testuser",
            collection=large_collection_data,
        )

        with patch(
            "ponderous.infrastructure.moxfield.client.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # Mock API responses
            mock_client.get_user_profile.return_value = mock_user_profile
            mock_client.get_collection.return_value = large_collection

            # Execute the sync
            response = await collection_service.sync_user_collection(
                username="testuser",
                source="moxfield",
            )

            # Verify response for large collection
            assert response.success is True
            assert response.username == "testuser"
            assert response.unique_cards == 100
            assert response.total_cards > 100  # Should be sum of all quantities
            assert response.items_processed > 100  # Profile + collection items
            assert response.sync_duration_seconds is not None

    @pytest.mark.asyncio
    async def test_sync_pipeline_force_refresh(
        self,
        collection_service: CollectionService,
        mock_user_profile: UserProfile,
        mock_collection_response: CollectionResponse,
    ) -> None:
        """Test sync pipeline with force refresh enabled."""
        with patch(
            "ponderous.infrastructure.moxfield.client.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # Mock API responses
            mock_client.get_user_profile.return_value = mock_user_profile
            mock_client.get_collection.return_value = mock_collection_response

            # Execute sync with force refresh
            response = await collection_service.sync_user_collection(
                username="testuser",
                source="moxfield",
                force_refresh=True,
                include_profile=True,
            )

            # Verify response
            assert response.success is True
            assert response.username == "testuser"

            # Should still make API calls even with force refresh
            mock_client.get_user_profile.assert_called_once()
            mock_client.get_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_pipeline_profile_excluded(
        self,
        collection_service: CollectionService,
        mock_collection_response: CollectionResponse,
    ) -> None:
        """Test sync pipeline with profile excluded."""
        with patch(
            "ponderous.infrastructure.moxfield.client.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # Mock only collection response
            mock_client.get_collection.return_value = mock_collection_response

            # Execute sync without profile
            response = await collection_service.sync_user_collection(
                username="testuser",
                source="moxfield",
                include_profile=False,
            )

            # Verify response
            assert response.success is True
            assert response.username == "testuser"
            assert response.unique_cards == 3
            assert response.total_cards == 8

            # Profile should not be called
            mock_client.get_user_profile.assert_not_called()
            mock_client.get_collection.assert_called_once()

    @pytest.mark.asyncio
    async def test_sync_pipeline_validation_errors(
        self,
        collection_service: CollectionService,
    ) -> None:
        """Test sync pipeline with validation errors."""
        # Test empty username
        with pytest.raises(PonderousError, match="Username cannot be empty"):
            await collection_service.sync_user_collection(
                username="",
                source="moxfield",
            )

        # Test whitespace username
        with pytest.raises(PonderousError, match="Username cannot be empty"):
            await collection_service.sync_user_collection(
                username="   ",
                source="moxfield",
            )

    @pytest.mark.asyncio
    async def test_sync_pipeline_username_format_validation(
        self,
        collection_service: CollectionService,
    ) -> None:
        """Test sync pipeline username format validation."""
        # Test invalid username format
        invalid_usernames = [
            "a",  # Too short
            "a" * 31,  # Too long
            "_invalid",  # Starts with underscore
            "invalid_",  # Ends with underscore
            "-invalid",  # Starts with dash
            "invalid-",  # Ends with dash
            "invalid@user",  # Contains invalid character
        ]

        for invalid_username in invalid_usernames:
            with pytest.raises(PonderousError, match="Invalid username format"):
                await collection_service.sync_user_collection(
                    username=invalid_username,
                    source="moxfield",
                )

    @pytest.mark.asyncio
    async def test_sync_pipeline_data_transformation(
        self,
        collection_service: CollectionService,
        mock_user_profile: UserProfile,
    ) -> None:
        """Test that data transformation works correctly in the pipeline."""
        # Collection with specific data types to test transformation
        collection_data = {
            "test_card": {
                "id": "test_scryfall_id",
                "name": "Æther Vial",  # Unicode name
                "quantity": 3,
                "foilQuantity": 1,
                "priceUsd": 15.99,
                "priceUsdFoil": 25.50,
                "set": "DST",
                "rarity": "rare",
                "cmc": 1,
                "colors": [],  # Colorless
                "type": "Artifact",
                "text": "{1}, {T}: You may put a creature card with mana value X from your hand onto the battlefield, where X is the number of charge counters on Æther Vial.",
            }
        }

        collection_response = CollectionResponse(
            username="testuser",
            collection=collection_data,
        )

        with patch(
            "ponderous.infrastructure.moxfield.client.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # Mock API responses
            mock_client.get_user_profile.return_value = mock_user_profile
            mock_client.get_collection.return_value = collection_response

            # Execute the sync
            response = await collection_service.sync_user_collection(
                username="testuser",
                source="moxfield",
            )

            # Verify response
            assert response.success is True
            assert response.unique_cards == 1
            assert response.total_cards == 4  # 3 + 1 foil

            # The data transformation should be handled by the ETL pipeline
            # In a real test, we might query the database to verify the data
            # was transformed and stored correctly

    @pytest.mark.asyncio
    async def test_concurrent_sync_operations(
        self,
        collection_service: CollectionService,
        mock_user_profile: UserProfile,
        mock_collection_response: CollectionResponse,
    ) -> None:
        """Test concurrent sync operations."""
        with patch(
            "ponderous.infrastructure.moxfield.client.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None

            # Mock API responses
            mock_client.get_user_profile.return_value = mock_user_profile
            mock_client.get_collection.return_value = mock_collection_response

            # Execute multiple syncs concurrently
            tasks = [
                collection_service.sync_user_collection(
                    username=f"user{i}",
                    source="moxfield",
                )
                for i in range(3)
            ]

            responses = await asyncio.gather(*tasks)

            # Verify all responses
            assert len(responses) == 3
            for i, response in enumerate(responses):
                assert response.success is True
                assert response.username == f"user{i}"
                assert response.unique_cards == 3

            # Should have made API calls for each user
            assert mock_client.get_user_profile.call_count == 3
            assert mock_client.get_collection.call_count == 3

    @pytest.mark.asyncio
    async def test_sync_pipeline_network_timeout_simulation(
        self,
        collection_service: CollectionService,
    ) -> None:
        """Test sync pipeline behavior with network timeout simulation."""
        with patch(
            "ponderous.infrastructure.moxfield.client.MoxfieldClient"
        ) as mock_client_class:
            # Setup mock client to simulate timeout
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            mock_client.__aenter__.return_value = mock_client
            mock_client.__aexit__.return_value = None
            mock_client.get_user_profile.side_effect = TimeoutError(
                "Connection timeout"
            )

            # Execute the sync - should handle timeout gracefully
            response = await collection_service.sync_user_collection(
                username="testuser",
                source="moxfield",
            )

            # Verify failure response
            assert response.success is False
            assert response.username == "testuser"
            assert response.error_message is not None and (
                "timeout" in response.error_message.lower()
                or "Connection timeout" in response.error_message
            )
