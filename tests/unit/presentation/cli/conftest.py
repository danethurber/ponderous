"""
Shared fixtures and configuration for CLI tests.

Provides common test utilities, fixtures, and mock objects
that can be reused across all CLI test modules.
"""

from collections.abc import Generator
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from ponderous.shared.config import PonderousConfig


@pytest.fixture
def cli_runner() -> CliRunner:
    """Create a Click test runner with isolated filesystem."""
    return CliRunner()


@pytest.fixture
def mock_config() -> Mock:
    """Create a mock configuration with all required attributes."""
    config = Mock(spec=PonderousConfig)
    config.debug = False

    # Database configuration
    config.database = Mock()
    config.database.path = Path.home() / ".ponderous" / "test.db"
    config.database.memory = False
    config.database.threads = 4

    # External API configurations
    config.moxfield = Mock()
    config.moxfield.base_url = "https://api2.moxfield.com/v2"
    config.moxfield.timeout = 30.0
    config.moxfield.rate_limit = 2.0

    config.edhrec = Mock()
    config.edhrec.base_url = "https://edhrec.com"
    config.edhrec.timeout = 30.0
    config.edhrec.rate_limit = 1.5

    # Analysis configuration
    config.analysis = Mock()
    config.analysis.min_completion_threshold = 0.7
    config.analysis.max_commanders_to_analyze = 1000
    config.analysis.cache_results = True

    # Logging configuration
    config.logging = Mock()
    config.logging.level = "INFO"
    config.logging.file_path = None

    # Application configuration
    config.config_dir = Path.home() / ".ponderous"

    return config


@pytest.fixture
def mock_db_connection() -> Mock:
    """Create a mock database connection."""
    db = Mock()
    db.fetch_all.return_value = []
    db.fetch_one.return_value = None
    db.execute.return_value = None
    db.close.return_value = None
    return db


@pytest.fixture
def mock_repositories() -> dict[str, Mock]:
    """Create mock repository objects."""
    return {
        "card_repo": Mock(),
        "commander_repo": Mock(),
        "collection_repo": Mock(),
        "deck_repo": Mock(),
    }


@pytest.fixture
def sample_collection_data() -> dict[str, Any]:
    """Sample collection data for testing."""
    return {
        "total_cards": 1250,
        "unique_cards": 875,
        "sets_represented": 45,
        "foil_cards": 120,
        "last_import": "2024-01-15 10:30:00",
    }


@pytest.fixture
def sample_commander_recommendations() -> list[dict[str, Any]]:
    """Sample commander recommendation data for testing."""
    return [
        {
            "commander_name": "Atraxa, Praetors' Voice",
            "color_identity": ["W", "U", "B", "G"],
            "completion_percentage": 0.85,
            "owned_cards": 68,
            "total_cards": 80,
            "missing_cards_value": 120.50,
            "power_level": 8.2,
            "archetype": "control",
            "buildability_score": 9.1,
        },
        {
            "commander_name": "Edgar Markov",
            "color_identity": ["R", "W", "B"],
            "completion_percentage": 0.72,
            "owned_cards": 58,
            "total_cards": 80,
            "missing_cards_value": 180.25,
            "power_level": 7.8,
            "archetype": "aggro",
            "buildability_score": 7.9,
        },
    ]


@pytest.fixture
def mock_import_response() -> Mock:
    """Mock import response for collection import tests."""
    response = Mock()
    response.success = True
    response.items_processed = 500
    response.items_imported = 485
    response.items_skipped = 15
    response.success_rate = 97.0
    response.processing_time_seconds = 2.5
    response.has_warnings = False
    response.warnings = []
    response.has_errors = False
    response.errors = []
    return response


@pytest.fixture
def patched_config(mock_config: Mock) -> Generator[Mock, None, None]:
    """Patch get_config() to return mock configuration."""
    with (
        patch("ponderous.shared.config.get_config") as mock_get_config,
        patch("ponderous.presentation.cli.base.get_config") as mock_cli_get_config,
    ):
        mock_get_config.return_value = mock_config
        mock_cli_get_config.return_value = mock_config
        yield mock_config


@pytest.fixture
def patched_db_connection(mock_db_connection: Mock) -> Generator[Mock, None, None]:
    """Patch database connection to return mock."""
    with patch(
        "ponderous.infrastructure.database.get_database_connection"
    ) as mock_get_db:
        mock_get_db.return_value = mock_db_connection
        yield mock_db_connection


@pytest.fixture
def isolated_filesystem(cli_runner: CliRunner) -> Generator[Path, None, None]:
    """Provide an isolated filesystem for file operations."""
    with cli_runner.isolated_filesystem():
        yield Path.cwd()
