"""Unit tests for EDHREC models."""

from datetime import datetime

import pytest

from ponderous.infrastructure.edhrec.models import (
    EDHRECCard,
    EDHRECCommander,
    EDHRECScrapingResult,
)


class TestEDHRECCard:
    """Test suite for EDHRECCard model."""

    def test_edhrec_card_creation_valid(self) -> None:
        """Should create EDHRECCard with valid data."""
        # Act
        card = EDHRECCard(
            name="Sol Ring",
            url_slug="sol-ring",
            inclusion_rate=0.85,
            synergy_score=0.0,
            category="staple",
            total_decks=50000,
            price_usd=2.50,
        )

        # Assert
        assert card.name == "Sol Ring"
        assert card.url_slug == "sol-ring"
        assert card.inclusion_rate == 0.85
        assert card.synergy_score == 0.0
        assert card.category == "staple"
        assert card.total_decks == 50000
        assert card.price_usd == 2.50

    def test_edhrec_card_creation_minimal(self) -> None:
        """Should create EDHRECCard with minimal required data."""
        # Act
        card = EDHRECCard(
            name="Lightning Bolt",
            url_slug="lightning-bolt",
            inclusion_rate=0.45,
            synergy_score=0.3,
            category="high_synergy",
            total_decks=25000,
        )

        # Assert
        assert card.name == "Lightning Bolt"
        assert card.price_usd is None  # Optional field

    def test_edhrec_card_frozen(self) -> None:
        """Should be immutable (frozen dataclass)."""
        # Arrange
        card = EDHRECCard(
            name="Test Card",
            url_slug="test-card",
            inclusion_rate=0.5,
            synergy_score=0.0,
            category="staple",
            total_decks=1000,
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            card.name = "Modified Name"  # Should fail - frozen

    def test_edhrec_card_inclusion_rate_validation(self) -> None:
        """Should validate inclusion_rate is between 0 and 1."""
        # Test invalid values
        invalid_rates = [-0.1, 1.1, 2.0, -1.0]

        for rate in invalid_rates:
            with pytest.raises(
                ValueError, match="Inclusion rate must be between 0 and 1"
            ):
                EDHRECCard(
                    name="Test Card",
                    url_slug="test",
                    inclusion_rate=rate,  # Invalid
                    synergy_score=0.0,
                    category="staple",
                    total_decks=1000,
                )

    def test_edhrec_card_synergy_score_validation(self) -> None:
        """Should validate synergy_score is between -1 and 1."""
        # Test invalid values
        invalid_scores = [-1.1, 1.1, 2.0, -2.0]

        for score in invalid_scores:
            with pytest.raises(
                ValueError, match="Synergy score must be between -1 and 1"
            ):
                EDHRECCard(
                    name="Test Card",
                    url_slug="test",
                    inclusion_rate=0.5,
                    synergy_score=score,  # Invalid
                    category="staple",
                    total_decks=1000,
                )

    def test_edhrec_card_total_decks_validation(self) -> None:
        """Should validate total_decks is not negative."""
        # Act & Assert
        with pytest.raises(ValueError, match="Total decks cannot be negative"):
            EDHRECCard(
                name="Test Card",
                url_slug="test",
                inclusion_rate=0.5,
                synergy_score=0.0,
                category="staple",
                total_decks=-1,  # Invalid
            )

    def test_edhrec_card_boundary_values(self) -> None:
        """Should accept boundary values correctly."""
        # Test boundary values that should be valid
        card = EDHRECCard(
            name="Boundary Test",
            url_slug="boundary-test",
            inclusion_rate=0.0,  # Minimum valid
            synergy_score=-1.0,  # Minimum valid
            category="basic",
            total_decks=0,  # Minimum valid
        )

        assert card.inclusion_rate == 0.0
        assert card.synergy_score == -1.0
        assert card.total_decks == 0

        # Test maximum boundary values
        card2 = EDHRECCard(
            name="Boundary Test 2",
            url_slug="boundary-test-2",
            inclusion_rate=1.0,  # Maximum valid
            synergy_score=1.0,  # Maximum valid
            category="signature",
            total_decks=999999,
        )

        assert card2.inclusion_rate == 1.0
        assert card2.synergy_score == 1.0


class TestEDHRECCommander:
    """Test suite for EDHRECCommander model."""

    def test_edhrec_commander_creation_full(self) -> None:
        """Should create EDHRECCommander with full data."""
        # Act
        commander = EDHRECCommander(
            name="Atraxa, Praetors' Voice",
            url_slug="atraxa-praetors-voice",
            color_identity="WUBG",
            total_decks=15000,
            popularity_rank=1,
            avg_deck_price=450.75,
            salt_score=2.5,
            power_level=8.0,
            archetype="Superfriends",
            themes=["Planeswalkers", "Counters", "+1/+1 Counters"],
        )

        # Assert
        assert commander.name == "Atraxa, Praetors' Voice"
        assert commander.url_slug == "atraxa-praetors-voice"
        assert commander.color_identity == "WUBG"
        assert commander.total_decks == 15000
        assert commander.popularity_rank == 1
        assert commander.avg_deck_price == 450.75
        assert commander.salt_score == 2.5
        assert commander.power_level == 8.0
        assert commander.archetype == "Superfriends"
        assert commander.themes == ["Planeswalkers", "Counters", "+1/+1 Counters"]

    def test_edhrec_commander_creation_minimal(self) -> None:
        """Should create EDHRECCommander with minimal required data."""
        # Act
        commander = EDHRECCommander(
            name="Zurgo Bellstriker",
            url_slug="zurgo-bellstriker",
            color_identity="R",
            total_decks=500,
            popularity_rank=250,
            avg_deck_price=125.0,
            salt_score=1.0,
            power_level=6.0,
        )

        # Assert
        assert commander.name == "Zurgo Bellstriker"
        assert commander.archetype is None  # Optional field
        assert commander.themes is None  # Optional field

    def test_edhrec_commander_frozen(self) -> None:
        """Should be immutable (frozen dataclass)."""
        # Arrange
        commander = EDHRECCommander(
            name="Test Commander",
            url_slug="test-commander",
            color_identity="U",
            total_decks=1000,
            popularity_rank=100,
            avg_deck_price=200.0,
            salt_score=2.0,
            power_level=7.0,
        )

        # Act & Assert
        with pytest.raises(AttributeError):
            commander.total_decks = 2000  # Should fail - frozen

    def test_edhrec_commander_total_decks_validation(self) -> None:
        """Should validate total_decks is not negative."""
        # Act & Assert
        with pytest.raises(ValueError, match="Total decks cannot be negative"):
            EDHRECCommander(
                name="Invalid Commander",
                url_slug="invalid",
                color_identity="B",
                total_decks=-1,  # Invalid
                popularity_rank=1,
                avg_deck_price=100.0,
                salt_score=1.0,
                power_level=5.0,
            )

    def test_edhrec_commander_popularity_rank_validation(self) -> None:
        """Should validate popularity_rank is at least 1."""
        # Act & Assert
        with pytest.raises(ValueError, match="Popularity rank must be at least 1"):
            EDHRECCommander(
                name="Invalid Commander",
                url_slug="invalid",
                color_identity="G",
                total_decks=1000,
                popularity_rank=0,  # Invalid
                avg_deck_price=100.0,
                salt_score=1.0,
                power_level=5.0,
            )

    def test_edhrec_commander_avg_deck_price_validation(self) -> None:
        """Should validate avg_deck_price is not negative."""
        # Act & Assert
        with pytest.raises(ValueError, match="Average deck price cannot be negative"):
            EDHRECCommander(
                name="Invalid Commander",
                url_slug="invalid",
                color_identity="W",
                total_decks=1000,
                popularity_rank=50,
                avg_deck_price=-10.0,  # Invalid
                salt_score=1.0,
                power_level=5.0,
            )

    def test_edhrec_commander_salt_score_validation(self) -> None:
        """Should validate salt_score is between 0 and 5."""
        # Test invalid values
        invalid_scores = [-0.1, 5.1, 10.0, -1.0]

        for score in invalid_scores:
            with pytest.raises(ValueError, match="Salt score must be between 0 and 5"):
                EDHRECCommander(
                    name="Invalid Commander",
                    url_slug="invalid",
                    color_identity="R",
                    total_decks=1000,
                    popularity_rank=50,
                    avg_deck_price=100.0,
                    salt_score=score,  # Invalid
                    power_level=5.0,
                )

    def test_edhrec_commander_power_level_validation(self) -> None:
        """Should validate power_level is between 1 and 10."""
        # Test invalid values
        invalid_levels = [0.9, 10.1, 15.0, 0.0]

        for level in invalid_levels:
            with pytest.raises(
                ValueError, match="Power level must be between 1 and 10"
            ):
                EDHRECCommander(
                    name="Invalid Commander",
                    url_slug="invalid",
                    color_identity="C",
                    total_decks=1000,
                    popularity_rank=50,
                    avg_deck_price=100.0,
                    salt_score=1.0,
                    power_level=level,  # Invalid
                )

    def test_edhrec_commander_boundary_values(self) -> None:
        """Should accept boundary values correctly."""
        # Test minimum boundary values
        commander_min = EDHRECCommander(
            name="Min Commander",
            url_slug="min-commander",
            color_identity="C",
            total_decks=0,  # Minimum valid
            popularity_rank=1,  # Minimum valid
            avg_deck_price=0.0,  # Minimum valid
            salt_score=0.0,  # Minimum valid
            power_level=1.0,  # Minimum valid
        )

        assert commander_min.total_decks == 0
        assert commander_min.popularity_rank == 1
        assert commander_min.avg_deck_price == 0.0
        assert commander_min.salt_score == 0.0
        assert commander_min.power_level == 1.0

        # Test maximum boundary values
        commander_max = EDHRECCommander(
            name="Max Commander",
            url_slug="max-commander",
            color_identity="WUBRG",
            total_decks=999999,
            popularity_rank=999999,
            avg_deck_price=9999.99,
            salt_score=5.0,  # Maximum valid
            power_level=10.0,  # Maximum valid
        )

        assert commander_max.salt_score == 5.0
        assert commander_max.power_level == 10.0

    def test_edhrec_commander_color_identity_values(self) -> None:
        """Should handle various color identity combinations."""
        # Test different color identity formats
        color_identities = [
            "C",  # Colorless
            "W",  # Mono white
            "U",  # Mono blue
            "B",  # Mono black
            "R",  # Mono red
            "G",  # Mono green
            "WU",  # Two colors
            "RBG",  # Three colors
            "WUBR",  # Four colors
            "WUBRG",  # Five colors
        ]

        for i, color_id in enumerate(color_identities, 1):
            commander = EDHRECCommander(
                name=f"Test Commander {i}",
                url_slug=f"test-commander-{i}",
                color_identity=color_id,
                total_decks=1000,
                popularity_rank=i,
                avg_deck_price=100.0,
                salt_score=2.0,
                power_level=7.0,
            )

            assert commander.color_identity == color_id


class TestEDHRECScrapingResult:
    """Test suite for EDHRECScrapingResult model."""

    def test_scraping_result_creation(self) -> None:
        """Should create EDHRECScrapingResult with valid data."""
        # Arrange
        timestamp = datetime.now()

        # Act
        result = EDHRECScrapingResult(
            success=True,
            commanders_found=5,
            decks_found=10,
            cards_found=150,
            processing_time_seconds=2.5,
            scraped_at=timestamp,
            errors=[],
            warnings=[],
        )

        # Assert
        assert result.success is True
        assert result.commanders_found == 5
        assert result.decks_found == 10
        assert result.cards_found == 150
        assert result.processing_time_seconds == 2.5
        assert result.scraped_at == timestamp
        assert result.errors == []
        assert result.warnings == []

    def test_scraping_result_with_errors(self) -> None:
        """Should handle scraping result with errors."""
        # Act
        result = EDHRECScrapingResult(
            success=False,
            commanders_found=0,
            decks_found=0,
            cards_found=0,
            processing_time_seconds=0.5,
            scraped_at=datetime.now(),
            errors=["Connection timeout", "Rate limit exceeded"],
            warnings=["Slow response time"],
        )

        # Assert
        assert result.success is False
        assert result.has_errors is True
        assert len(result.errors) == 2
        assert "Connection timeout" in result.errors
        assert "Rate limit exceeded" in result.errors
        assert len(result.warnings) == 1
        assert "Slow response time" in result.warnings

    def test_scraping_result_mutable(self) -> None:
        """Should be mutable (not frozen dataclass)."""
        # Arrange
        result = EDHRECScrapingResult(
            success=True,
            commanders_found=1,
            decks_found=2,
            cards_found=50,
            processing_time_seconds=1.0,
            scraped_at=datetime.now(),
            errors=[],
            warnings=[],
        )

        # Act
        result.success = False  # Should work - not frozen

        # Assert
        assert result.success is False

    def test_scraping_result_success_rate(self) -> None:
        """Should calculate success rate correctly."""
        # Test successful scraping with items found
        result_with_items = EDHRECScrapingResult(
            success=True,
            commanders_found=5,
            decks_found=10,
            cards_found=100,
            processing_time_seconds=2.0,
            scraped_at=datetime.now(),
        )

        assert result_with_items.success_rate == 1.0

        # Test failed scraping
        result_failed = EDHRECScrapingResult(
            success=False,
            commanders_found=0,
            decks_found=0,
            cards_found=0,
            processing_time_seconds=0.1,
            scraped_at=datetime.now(),
        )

        assert result_failed.success_rate == 0.0

        # Test successful scraping with no items
        result_no_items = EDHRECScrapingResult(
            success=True,
            commanders_found=0,
            decks_found=0,
            cards_found=0,
            processing_time_seconds=1.0,
            scraped_at=datetime.now(),
        )

        assert result_no_items.success_rate == 0.0
