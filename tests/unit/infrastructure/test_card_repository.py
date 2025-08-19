"""Tests for card repository implementation."""

import pytest

from ponderous.domain.models.card import Card
from ponderous.infrastructure.database import CardRepositoryImpl, DatabaseConnection
from ponderous.shared.config import DatabaseConfig


class TestCardRepositoryImpl:
    """Test cases for CardRepositoryImpl."""

    @pytest.fixture
    def repository(self) -> CardRepositoryImpl:
        """Create repository instance with in-memory database."""
        config = DatabaseConfig(memory=True, threads=1)
        db_connection = DatabaseConnection(config)
        return CardRepositoryImpl(db_connection)

    @pytest.fixture
    def sample_card(self) -> Card:
        """Create a sample card for testing."""
        return Card(
            card_id="test_card_1",
            name="Lightning Bolt",
            mana_cost="{R}",
            cmc=1,
            color_identity=["R"],
            type_line="Instant",
            oracle_text="Lightning Bolt deals 3 damage to any target.",
            rarity="common",
            set_code="LEA",
            collector_number="1",
            price_usd=0.50,
        )

    def test_store_and_get_by_id(
        self, repository: CardRepositoryImpl, sample_card: Card
    ) -> None:
        """Test storing and retrieving card by ID."""
        # Store card
        repository.store(sample_card)

        # Retrieve card
        result = repository.get_by_id(sample_card.card_id)

        assert result is not None
        assert result.card_id == sample_card.card_id
        assert result.name == sample_card.name
        assert result.mana_cost == sample_card.mana_cost
        assert result.color_identity == sample_card.color_identity

    def test_get_by_name(
        self, repository: CardRepositoryImpl, sample_card: Card
    ) -> None:
        """Test retrieving cards by name."""
        repository.store(sample_card)

        results = repository.get_by_name("Lightning Bolt")

        assert len(results) == 1
        assert results[0].name == "Lightning Bolt"

    def test_get_by_name_case_insensitive(
        self, repository: CardRepositoryImpl, sample_card: Card
    ) -> None:
        """Test case-insensitive name search."""
        repository.store(sample_card)

        results = repository.get_by_name("lightning bolt")
        assert len(results) == 1

        results = repository.get_by_name("LIGHTNING BOLT")
        assert len(results) == 1

    def test_get_by_color_identity(
        self, repository: CardRepositoryImpl, sample_card: Card
    ) -> None:
        """Test retrieving cards by color identity."""
        repository.store(sample_card)

        # Test exact color identity match
        results = repository.get_by_color_identity(["R"])
        assert len(results) == 1
        assert results[0].name == "Lightning Bolt"

        # Test non-matching color identity
        results = repository.get_by_color_identity(["U"])
        assert len(results) == 0

    def test_search_by_partial_name(
        self, repository: CardRepositoryImpl, sample_card: Card
    ) -> None:
        """Test partial name search."""
        repository.store(sample_card)

        results = repository.search_by_partial_name("Light")
        assert len(results) == 1
        assert results[0].name == "Lightning Bolt"

        results = repository.search_by_partial_name("Bolt")
        assert len(results) == 1

        results = repository.search_by_partial_name("Missing")
        assert len(results) == 0

    def test_get_commanders(self, repository: CardRepositoryImpl) -> None:
        """Test getting commander cards."""
        # Create a legendary creature
        commander_card = Card(
            card_id="commander_1",
            name="Jace, Vryn's Prodigy",
            type_line="Legendary Creature — Human Wizard",
            color_identity=["U"],
        )
        repository.store(commander_card)

        # Create a non-commander
        non_commander = Card(
            card_id="not_commander",
            name="Lightning Bolt",
            type_line="Instant",
            color_identity=["R"],
        )
        repository.store(non_commander)

        commanders = repository.get_commanders()
        assert len(commanders) == 1
        assert commanders[0].name == "Jace, Vryn's Prodigy"

    def test_store_batch(self, repository: CardRepositoryImpl) -> None:
        """Test batch storage of cards."""
        cards = [
            Card(card_id="card1", name="Card 1"),
            Card(card_id="card2", name="Card 2"),
            Card(card_id="card3", name="Card 3"),
        ]

        stored_count, skipped_count = repository.store_batch(cards)

        assert stored_count == 3
        assert skipped_count == 0

        # Verify cards were stored
        assert repository.get_by_id("card1") is not None
        assert repository.get_by_id("card2") is not None
        assert repository.get_by_id("card3") is not None

    def test_get_card_stats(
        self, repository: CardRepositoryImpl, sample_card: Card
    ) -> None:
        """Test card statistics."""
        # Empty database
        stats = repository.get_card_stats()
        assert stats["total_cards"] == 0

        # After storing a card
        repository.store(sample_card)
        stats = repository.get_card_stats()
        assert stats["total_cards"] == 1
        assert stats["unique_names"] == 1

    def test_find_matching_cards(
        self, repository: CardRepositoryImpl, sample_card: Card
    ) -> None:
        """Test finding cards that match collection import data."""
        repository.store(sample_card)

        # Test exact name match
        matches = repository.find_matching_cards("Lightning Bolt")
        assert len(matches) == 1
        assert matches[0].name == "Lightning Bolt"

        # Test with set
        matches = repository.find_matching_cards("Lightning Bolt", "LEA")
        assert len(matches) == 1

        # Test no match
        matches = repository.find_matching_cards("Nonexistent Card")
        assert len(matches) == 0

    def test_normalize_card_name(self, repository: CardRepositoryImpl) -> None:
        """Test card name normalization."""
        normalized = repository.normalize_card_name("  lightning bolt  ")
        assert normalized == "Lightning Bolt"

        normalized = repository.normalize_card_name("JACE, VRYN'S PRODIGY")
        assert normalized == "Jace, Vryn'S Prodigy"
