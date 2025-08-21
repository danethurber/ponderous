"""
Mock objects and factories for CLI testing.

Provides reusable mock objects that simulate external dependencies
and services used by CLI commands.
"""

from typing import Any
from unittest.mock import AsyncMock, Mock

from ponderous.domain.models.card import Card


class MockRepositoryFactory:
    """Factory for creating mock repository objects."""

    @staticmethod
    def create_card_repository() -> Mock:
        """Create a mock card repository."""
        repo = Mock()
        repo.search_by_partial_name.return_value = []
        repo.get_commanders.return_value = []
        repo.get_card_stats.return_value = {
            "total_cards": 0,
            "unique_names": 0,
            "sets_count": 0,
        }
        repo.store_batch.return_value = (0, 0)  # (stored, skipped)
        return repo

    @staticmethod
    def create_commander_repository() -> Mock:
        """Create a mock commander repository."""
        repo = Mock()
        repo.get_recommendations_for_collection.return_value = []
        repo.calculate_buildability_score.return_value = 0.0
        repo.store_batch.return_value = (0, 0)
        return repo

    @staticmethod
    def create_collection_repository() -> Mock:
        """Create a mock collection repository."""
        repo = Mock()
        repo.get_user_collection_summary.return_value = {
            "total_cards": 0,
            "unique_cards": 0,
            "sets_represented": 0,
            "foil_cards": 0,
        }
        return repo


class MockServiceFactory:
    """Factory for creating mock service objects."""

    @staticmethod
    def create_recommendation_service() -> Mock:
        """Create a mock recommendation service."""
        service = Mock()
        service.get_commander_recommendations.return_value = []
        service.get_deck_recommendations.return_value = []
        return service

    @staticmethod
    def create_collection_service() -> Mock:
        """Create a mock collection service."""
        service = Mock()
        service.analyze_collection.return_value = {}
        return service


class MockImporterFactory:
    """Factory for creating mock importer objects."""

    @staticmethod
    def create_moxfield_importer() -> Mock:
        """Create a mock Moxfield CSV importer."""
        importer = Mock()

        # Mock successful import response
        response = Mock()
        response.success = True
        response.items_processed = 100
        response.items_imported = 95
        response.items_skipped = 5
        response.success_rate = 95.0
        response.processing_time_seconds = 1.5
        response.has_warnings = False
        response.warnings = []
        response.has_errors = False
        response.errors = []

        importer.import_collection.return_value = response
        return importer


class MockEDHRECFactory:
    """Factory for creating mock EDHREC-related objects."""

    @staticmethod
    def create_scraper() -> AsyncMock:
        """Create a mock EDHREC scraper."""
        scraper = AsyncMock()
        scraper.get_popular_commanders.return_value = []
        scraper.get_paginated_commanders.return_value = []
        return scraper

    @staticmethod
    def create_commander_data() -> list[dict[str, Any]]:
        """Create sample EDHREC commander data."""
        return [
            {
                "name": "Atraxa, Praetors' Voice",
                "url_slug": "atraxa-praetors-voice",
                "color_identity": "WUBG",
                "total_decks": 12500,
                "popularity_rank": 1,
                "avg_deck_price": 250.0,
                "salt_score": 2.1,
                "power_level": 8.2,
            },
            {
                "name": "Edgar Markov",
                "url_slug": "edgar-markov",
                "color_identity": "RWB",
                "total_decks": 8200,
                "popularity_rank": 2,
                "avg_deck_price": 180.0,
                "salt_score": 1.8,
                "power_level": 7.8,
            },
        ]


class MockCardFactory:
    """Factory for creating mock card objects."""

    @staticmethod
    def create_sample_cards() -> list[Card]:
        """Create a list of sample card objects."""
        return [
            Card(
                card_id="lightning_bolt_lea",
                name="Lightning Bolt",
                mana_cost="{R}",
                cmc=1,
                color_identity=["R"],
                type_line="Instant",
                oracle_text="Lightning Bolt deals 3 damage to any target.",
                rarity="common",
                set_code="LEA",
                collector_number="1",
                price_usd=25.00,
            ),
            Card(
                card_id="sol_ring_lea",
                name="Sol Ring",
                mana_cost="{1}",
                cmc=1,
                color_identity=[],
                type_line="Artifact",
                oracle_text="{T}: Add {C}{C}.",
                rarity="uncommon",
                set_code="LEA",
                collector_number="2",
                price_usd=150.00,
            ),
        ]

    @staticmethod
    def create_commander_card() -> Card:
        """Create a sample commander card."""
        return Card(
            card_id="atraxa_praetors_voice",
            name="Atraxa, Praetors' Voice",
            mana_cost="{2}{W}{U}{B}{G}",
            cmc=4,
            color_identity=["W", "U", "B", "G"],
            type_line="Legendary Creature — Phyrexian Angel Horror",
            oracle_text="Flying, vigilance, deathtouch, lifelink",
            power="4",
            toughness="4",
            rarity="mythic",
            set_code="C16",
            collector_number="28",
            price_usd=25.00,
        )
