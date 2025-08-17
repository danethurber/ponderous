"""Pytest configuration and shared fixtures."""

import pytest
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from unittest.mock import Mock

from ponderous.domain.models import (
    Card,
    CardData,
    Collection,
    CollectionItem,
    Commander,
    DeckRecommendation,
    User,
    MissingCard,
)
from ponderous.shared.config import PonderousConfig


@pytest.fixture
def temp_db_path(tmp_path: Path) -> Path:
    """Create a temporary database path for testing."""
    return tmp_path / "test_ponderous.db"


@pytest.fixture
def test_config(temp_db_path: Path) -> PonderousConfig:
    """Create test configuration with temporary database."""
    config = PonderousConfig()
    config.database.path = temp_db_path
    config.database.memory = True  # Use in-memory database for tests
    config.logging.level = "DEBUG"
    return config


@pytest.fixture
def sample_user() -> User:
    """Create a sample user for testing."""
    return User(
        user_id="test_user",
        username="testuser",
        display_name="Test User",
        created_at=datetime(2023, 1, 1),
        last_sync=datetime(2023, 8, 1),
        total_cards=500,
        total_value=2500.0,
    )


@pytest.fixture
def sample_cards() -> List[Card]:
    """Create sample cards for testing."""
    return [
        Card(
            name="Meren of Clan Nel Toth",
            card_id="meren_001",
            cmc=5,
            color_identity=["B", "G"],
            type_line="Legendary Creature — Human Shaman",
            rarity="mythic",
            price_usd=15.50,
        ),
        Card(
            name="Sol Ring",
            card_id="sol_ring_001",
            cmc=1,
            color_identity=[],
            type_line="Artifact",
            rarity="uncommon",
            price_usd=2.00,
        ),
        Card(
            name="Lightning Bolt",
            card_id="bolt_001",
            cmc=1,
            color_identity=["R"],
            type_line="Instant",
            rarity="common",
            price_usd=0.50,
        ),
        Card(
            name="Swamp",
            card_id="swamp_001",
            cmc=0,
            color_identity=["B"],
            type_line="Basic Land — Swamp",
            rarity="common",
            price_usd=0.10,
        ),
    ]


@pytest.fixture
def sample_collection_items(sample_user: User) -> List[CollectionItem]:
    """Create sample collection items for testing."""
    return [
        CollectionItem(
            user_id=sample_user.user_id,
            source_id="moxfield",
            card_id="meren_001",
            card_name="Meren of Clan Nel Toth",
            quantity=1,
            foil_quantity=0,
            last_updated=datetime(2023, 8, 1),
        ),
        CollectionItem(
            user_id=sample_user.user_id,
            source_id="moxfield",
            card_id="sol_ring_001",
            card_name="Sol Ring",
            quantity=3,
            foil_quantity=1,
            last_updated=datetime(2023, 8, 1),
        ),
        CollectionItem(
            user_id=sample_user.user_id,
            source_id="moxfield",
            card_id="swamp_001",
            card_name="Swamp",
            quantity=20,
            foil_quantity=0,
            last_updated=datetime(2023, 8, 1),
        ),
    ]


@pytest.fixture
def sample_collection(
    sample_user: User, sample_collection_items: List[CollectionItem]
) -> Collection:
    """Create a sample collection for testing."""
    return Collection.from_items(sample_user.user_id, sample_collection_items)


@pytest.fixture
def sample_card_data() -> List[CardData]:
    """Create sample card data for deck analysis testing."""
    return [
        CardData(
            name="Meren of Clan Nel Toth",
            card_id="meren_001",
            inclusion_rate=1.0,
            synergy_score=3.0,
            category="signature",
            price_usd=15.50,
        ),
        CardData(
            name="Sol Ring",
            card_id="sol_ring_001",
            inclusion_rate=0.95,
            synergy_score=0.5,
            category="staple",
            price_usd=2.00,
        ),
        CardData(
            name="Eternal Witness",
            card_id="e_witness_001",
            inclusion_rate=0.78,
            synergy_score=2.5,
            category="high_synergy",
            price_usd=3.50,
        ),
        CardData(
            name="Golgari Signet",
            card_id="gol_signet_001",
            inclusion_rate=0.65,
            synergy_score=1.0,
            category="staple",
            price_usd=1.50,
        ),
    ]


@pytest.fixture
def sample_commander() -> Commander:
    """Create a sample commander for testing."""
    return Commander(
        name="Meren of Clan Nel Toth",
        card_id="meren_001",
        color_identity=["B", "G"],
        total_decks=8234,
        popularity_rank=15,
        avg_deck_price=450.50,
        salt_score=1.2,
        power_level=8.5,
    )


@pytest.fixture
def sample_deck_recommendation() -> DeckRecommendation:
    """Create a sample deck recommendation for testing."""
    return DeckRecommendation(
        commander_name="Meren of Clan Nel Toth",
        archetype="combo",
        theme="reanimator",
        budget_range="mid",
        completion_percentage=0.873,
        buildability_score=8.7,
        owned_cards=78,
        total_cards=89,
        missing_cards_value=67.50,
        missing_high_impact_cards=2,
    )


@pytest.fixture
def sample_missing_cards(sample_card_data: List[CardData]) -> List[MissingCard]:
    """Create sample missing cards for testing."""
    return [
        MissingCard.from_card_data(
            card_data=sample_card_data[2],  # Eternal Witness
            estimated_cost=3.50,
            alternatives=["Regrowth", "Nature's Spiral"],
        ),
        MissingCard.from_card_data(
            card_data=sample_card_data[3],  # Golgari Signet
            estimated_cost=1.50,
            alternatives=["Golgari Locket", "Commander's Sphere"],
        ),
    ]


@pytest.fixture
def mock_moxfield_response() -> Dict:
    """Mock Moxfield API response for testing."""
    return {
        "collection": {
            "cards": [
                {
                    "card": {
                        "id": "meren_001",
                        "name": "Meren of Clan Nel Toth",
                        "cmc": 5,
                        "color_identity": ["B", "G"],
                        "type_line": "Legendary Creature — Human Shaman",
                    },
                    "quantity": 1,
                    "foil_quantity": 0,
                },
                {
                    "card": {
                        "id": "sol_ring_001",
                        "name": "Sol Ring",
                        "cmc": 1,
                        "color_identity": [],
                        "type_line": "Artifact",
                    },
                    "quantity": 3,
                    "foil_quantity": 1,
                },
            ]
        }
    }


@pytest.fixture
def mock_edhrec_html() -> str:
    """Mock EDHREC HTML response for testing."""
    return """
    <html>
        <head><title>Meren of Clan Nel Toth EDHREC</title></head>
        <body>
            <div class="commander-stats">
                <span class="deck-count">8,234</span>
                <span class="avg-price">$450.50</span>
                <span class="power-level">8.5</span>
            </div>
            <div class="card-list">
                <div class="card-item" data-name="Sol Ring">
                    <span class="inclusion-rate">95%</span>
                    <span class="synergy-score">+5%</span>
                </div>
                <div class="card-item" data-name="Eternal Witness">
                    <span class="inclusion-rate">78%</span>
                    <span class="synergy-score">+25%</span>
                </div>
            </div>
        </body>
    </html>
    """


@pytest.fixture
def mock_database():
    """Create a mock database for testing."""
    return Mock()


# Pytest markers for different test categories
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "unit: Unit tests")
    config.addinivalue_line("markers", "integration: Integration tests")
    config.addinivalue_line("markers", "e2e: End-to-end tests")
    config.addinivalue_line("markers", "slow: Slow tests")
    config.addinivalue_line("markers", "moxfield: Tests involving Moxfield API")
    config.addinivalue_line("markers", "edhrec: Tests involving EDHREC scraping")
    config.addinivalue_line("markers", "database: Tests involving database operations")


# Auto-apply markers based on test location
def pytest_collection_modifyitems(config, items):
    """Automatically apply markers based on test file location."""
    for item in items:
        # Add unit marker to tests in unit/ directory
        if "unit" in str(item.fspath):
            item.add_marker(pytest.mark.unit)

        # Add integration marker to tests in integration/ directory
        elif "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)

        # Add e2e marker to tests in e2e/ directory
        elif "e2e" in str(item.fspath):
            item.add_marker(pytest.mark.e2e)

        # Add specific markers based on test name patterns
        if "moxfield" in item.name.lower() or "moxfield" in str(item.fspath):
            item.add_marker(pytest.mark.moxfield)

        if "edhrec" in item.name.lower() or "edhrec" in str(item.fspath):
            item.add_marker(pytest.mark.edhrec)

        if "database" in item.name.lower() or "database" in str(item.fspath):
            item.add_marker(pytest.mark.database)
