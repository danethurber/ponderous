"""Unit tests for RecommendationService."""

from unittest.mock import Mock

import pytest

from ponderous.application.services.recommendation_service import RecommendationService
from ponderous.domain.models.card import Card
from ponderous.domain.models.commander import CommanderRecommendation
from ponderous.domain.repositories.card_repository import CardRepository
from ponderous.domain.repositories.commander_repository import CommanderRepository
from ponderous.infrastructure.database.repositories.collection_repository import (
    CollectionRepository,
)


class TestRecommendationService:
    """Test suite for RecommendationService."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.card_repo = Mock(spec=CardRepository)
        self.commander_repo = Mock(spec=CommanderRepository)
        self.collection_repo = Mock(spec=CollectionRepository)

        self.service = RecommendationService(
            card_repo=self.card_repo,
            commander_repo=self.commander_repo,
            collection_repo=self.collection_repo,
        )

    def test_get_commander_recommendations_empty_collection(self) -> None:
        """Should return empty list for user with no collection."""
        # Arrange
        self.collection_repo.get_user_collection_summary.return_value = {
            "total_cards": 0,
            "total_value": 0.0,
        }

        # Act
        recommendations = self.service.get_commander_recommendations("user123")

        # Assert
        assert recommendations == []
        self.collection_repo.get_user_collection_summary.assert_called_once_with(
            "user123"
        )

    def test_buildability_score_calculation_basic(self) -> None:
        """Should calculate buildability score based on owned cards and EDHREC data."""
        # This test defines what the real algorithm should do
        # Current implementation uses placeholders - we need to replace it

        # Arrange
        owned_cards = {"Sol Ring", "Command Tower", "Lightning Bolt"}
        deck_cards = [
            # Mock EDHREC card data with inclusion rates and categories
            MockEDHRECCard(
                "Sol Ring", inclusion_rate=0.85, category="staple", synergy_score=0.0
            ),
            MockEDHRECCard(
                "Command Tower",
                inclusion_rate=0.70,
                category="staple",
                synergy_score=0.0,
            ),
            MockEDHRECCard(
                "Lightning Bolt",
                inclusion_rate=0.45,
                category="high_synergy",
                synergy_score=0.3,
            ),
            MockEDHRECCard(
                "Demonic Tutor",
                inclusion_rate=0.60,
                category="signature",
                synergy_score=0.8,
            ),
            MockEDHRECCard(
                "Swamp", inclusion_rate=0.90, category="basic", synergy_score=0.0
            ),
        ]

        # Act - this should use real algorithm, not current placeholder
        score = self.service.calculate_buildability_score(owned_cards, deck_cards)

        # Assert - weighted calculation based on categories and synergy
        # Expected calculation:
        # - Owned staples (Sol Ring, Command Tower): high weight
        # - Owned high synergy (Lightning Bolt): medium-high weight
        # - Missing signature (Demonic Tutor): high impact penalty
        # - Basic lands: low weight
        expected_score = pytest.approx(6.2, rel=0.1)  # Reasonable score for 3/5 owned
        assert score == expected_score

    def test_buildability_score_perfect_collection(self) -> None:
        """Should return 10.0 for complete deck ownership."""
        # Arrange
        deck_cards = [
            MockEDHRECCard(
                "Sol Ring", inclusion_rate=0.85, category="staple", synergy_score=0.0
            ),
            MockEDHRECCard(
                "Demonic Tutor",
                inclusion_rate=0.60,
                category="signature",
                synergy_score=0.8,
            ),
        ]
        owned_cards = {"Sol Ring", "Demonic Tutor"}

        # Act
        score = self.service.calculate_buildability_score(owned_cards, deck_cards)

        # Assert
        assert score == 10.0

    def test_buildability_score_empty_collection(self) -> None:
        """Should return 0.0 for empty collection."""
        # Arrange
        owned_cards = set()
        deck_cards = [
            MockEDHRECCard(
                "Sol Ring", inclusion_rate=0.85, category="staple", synergy_score=0.0
            ),
        ]

        # Act
        score = self.service.calculate_buildability_score(owned_cards, deck_cards)

        # Assert
        assert score == 0.0

    def test_category_weights_in_scoring(self) -> None:
        """Should weight card categories differently in buildability scoring."""
        # Test that signature cards have higher impact than basic lands

        # Arrange - own signature card vs basic land
        signature_owned = {"Demonic Tutor"}
        basic_owned = {"Swamp"}

        deck_cards = [
            MockEDHRECCard(
                "Demonic Tutor",
                inclusion_rate=0.60,
                category="signature",
                synergy_score=0.8,
            ),
            MockEDHRECCard(
                "Swamp", inclusion_rate=0.90, category="basic", synergy_score=0.0
            ),
            MockEDHRECCard(
                "Lightning Bolt",
                inclusion_rate=0.45,
                category="high_synergy",
                synergy_score=0.3,
            ),
        ]

        # Act
        signature_score = self.service.calculate_buildability_score(
            signature_owned, deck_cards
        )
        basic_score = self.service.calculate_buildability_score(basic_owned, deck_cards)

        # Assert - owning signature card should score higher than basic land
        assert signature_score > basic_score

    def test_synergy_score_impact(self) -> None:
        """Should factor synergy scores into buildability calculation."""
        # Arrange
        owned_cards = {"High Synergy Card"}

        high_synergy_deck = [
            MockEDHRECCard(
                "High Synergy Card",
                inclusion_rate=0.50,
                category="high_synergy",
                synergy_score=0.9,
            ),
            MockEDHRECCard(
                "Other Card", inclusion_rate=0.50, category="staple", synergy_score=0.0
            ),
        ]

        low_synergy_deck = [
            MockEDHRECCard(
                "High Synergy Card",
                inclusion_rate=0.50,
                category="high_synergy",
                synergy_score=0.1,
            ),
            MockEDHRECCard(
                "Other Card", inclusion_rate=0.50, category="staple", synergy_score=0.0
            ),
        ]

        # Act
        high_synergy_score = self.service.calculate_buildability_score(
            owned_cards, high_synergy_deck
        )
        low_synergy_score = self.service.calculate_buildability_score(
            owned_cards, low_synergy_deck
        )

        # Assert
        assert high_synergy_score > low_synergy_score

    def test_get_commander_recommendations_with_real_data_integration(self) -> None:
        """Should integrate with EDHREC data for realistic recommendations."""
        # This test defines how the service should work with real EDHREC data
        # Current implementation uses hardcoded placeholders

        # Arrange
        self.collection_repo.get_user_collection_summary.return_value = {
            "total_cards": 500,
            "total_value": 1000.0,
        }

        # Mock owned commanders in collection
        self.card_repo.get_commanders.return_value = [
            Card(
                name="Meren of Clan Nel Toth",
                card_id="meren_001",
                color_identity=["B", "G"],
            ),
            Card(
                name="Atraxa, Praetors' Voice",
                card_id="atraxa_001",
                color_identity=["W", "U", "B", "G"],
            ),
        ]

        # Mock EDHREC data for commanders
        from ponderous.domain.models.commander import Commander

        mock_commander = Commander(
            name="Meren of Clan Nel Toth",
            card_id="meren_001",
            color_identity=["B", "G"],
            total_decks=2500,
            popularity_rank=15,
            avg_deck_price=320.0,
            power_level=7.5,
            salt_score=2.0,
        )
        self.commander_repo.get_by_name.return_value = mock_commander

        # Mock collection analysis with cards that match our mock deck
        # Include many cards that will be in the generated mock deck
        self.collection_repo.get_collection_by_user.return_value = [
            {"card_name": "Sol Ring", "quantity": 1},
            {"card_name": "Demonic Tutor", "quantity": 1},
            {"card_name": "Command Tower", "quantity": 1},
            {"card_name": "Arcane Signet", "quantity": 1},
            {"card_name": "Rhystic Study", "quantity": 1},
            {"card_name": "Smothering Tithe", "quantity": 1},
            {"card_name": "Skullclamp", "quantity": 1},
            {"card_name": "Island", "quantity": 5},
            {"card_name": "Plains", "quantity": 5},
            {"card_name": "Swamp", "quantity": 8},  # For B/G deck
            {"card_name": "Forest", "quantity": 8},  # For B/G deck
        ]

        # Act
        recommendations = self.service.get_commander_recommendations(
            user_id="user123",
            color_preferences=["B", "G"],
            min_completion=0.3,  # Lower threshold to test algorithm works
            limit=10,
        )

        # Assert
        assert len(recommendations) > 0
        assert all(isinstance(rec, CommanderRecommendation) for rec in recommendations)

        # Verify realistic data instead of placeholders
        first_rec = recommendations[0]
        assert first_rec.commander_name in [
            "Meren of Clan Nel Toth",
            "Atraxa, Praetors' Voice",
        ]
        assert (
            first_rec.completion_percentage > 0.15
        )  # Should be more than placeholder 15%
        assert first_rec.buildability_score == pytest.approx(
            first_rec.completion_percentage * 10, rel=0.001
        )  # Should match our algorithm
        assert (
            first_rec.avg_deck_price == 320.0
        )  # Real EDHREC data, not hardcoded 250.0
        assert (
            first_rec.archetype == "midrange"
        )  # Real archetype from EDHREC, not "General Value"
        assert first_rec.popularity_rank == 15  # Real EDHREC popularity
        assert first_rec.popularity_count == 2500  # Real EDHREC total decks
        assert first_rec.owned_cards == 11  # Based on our mock collection
        assert first_rec.total_cards == 19  # Based on our mock deck generation

    def test_collection_synergy_calculation_realistic(self) -> None:
        """Should calculate realistic collection synergy beyond simple name matching."""
        # Current implementation uses naive string matching
        # Real implementation should use EDHREC categories and themes

        # Arrange
        user_id = "user123"
        commander_name = "Meren of Clan Nel Toth"

        # Mock collection with graveyard synergy cards
        self.collection_repo.get_collection_by_user.return_value = [
            {"card_name": "Entomb", "quantity": 1},
            {"card_name": "Reanimate", "quantity": 1},
            {"card_name": "Buried Alive", "quantity": 1},
            {"card_name": "Sol Ring", "quantity": 1},  # Generic staple
        ]

        # Act
        synergy_data = self.service.calculate_collection_synergy(
            user_id, commander_name
        )

        # Assert - should detect graveyard synergy theme, not just string matching
        assert synergy_data["synergy_score"] > 0.5  # High synergy with graveyard cards
        assert synergy_data["synergy_category"] in ["High", "Medium"]
        assert "graveyard_cards" in synergy_data or "theme_match" in synergy_data


class MockEDHRECCard:
    """Mock EDHREC card data for testing."""

    def __init__(
        self, name: str, inclusion_rate: float, category: str, synergy_score: float
    ):
        self.name = name
        self.inclusion_rate = inclusion_rate  # 0.0 to 1.0
        self.category = category  # "signature", "high_synergy", "staple", "basic"
        self.synergy_score = synergy_score  # 0.0 to 1.0


# Additional test helper functions
def create_mock_collection_data(cards: list[tuple[str, int]]) -> list[dict]:
    """Create mock collection data for testing."""
    return [{"card_name": name, "quantity": qty} for name, qty in cards]


def create_mock_edhrec_deck_data(**kwargs) -> dict:
    """Create mock EDHREC deck data with defaults."""
    defaults = {
        "total_decks": 1000,
        "popularity_rank": 100,
        "avg_deck_price": 300.0,
        "power_level": 7.0,
        "salt_score": 2.0,
        "archetype_distribution": {"midrange": 1.0},
    }
    defaults.update(kwargs)
    return defaults
