"""
Unit tests for the CLI module.

Tests cover command parsing, argument validation, error handling,
and output formatting for all CLI commands.
"""

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock, patch

if TYPE_CHECKING:
    from click.testing import CliRunner

import pytest
from click.testing import CliRunner

from ponderous.cli import PonderousContext, cli
from ponderous.shared.config import PonderousConfig
from ponderous.shared.exceptions import PonderousError


@pytest.fixture
def runner() -> CliRunner:
    """Create a Click test runner."""
    return CliRunner()


@pytest.fixture
def mock_config() -> Mock:
    """Create a mock configuration."""
    config = Mock(spec=PonderousConfig)
    config.debug = False

    # Set up nested mock objects
    config.database = Mock()
    config.database.path = Path.home() / ".ponderous" / "test.db"

    config.moxfield = Mock()
    config.moxfield.base_url = "https://api.moxfield.com"

    config.edhrec = Mock()
    config.edhrec.base_url = "https://edhrec.com"

    config.analysis = Mock()
    config.analysis.min_completion_threshold = 0.7

    config.logging = Mock()
    config.logging.level = "INFO"
    config.logging.file_path = None

    config.config_dir = Path.home() / ".ponderous"
    return config


@pytest.fixture
def mock_context() -> Mock:
    """Create a mock CLI context."""
    context = Mock(spec=PonderousContext)
    context.debug = False
    context.verbose = False
    return context


class TestCLIMain:
    """Test main CLI entry point and global options."""

    def test_cli_help(self, runner: CliRunner) -> None:
        """Test that CLI help is displayed correctly."""
        result = runner.invoke(cli, ["--help"])

        assert result.exit_code == 0
        assert "Ponderous" in result.output
        assert "Thoughtful analysis of your MTG collection" in result.output
        assert "discover-commanders" in result.output
        assert "sync-collection" in result.output

    def test_cli_version(self, runner: CliRunner) -> None:
        """Test version display."""
        result = runner.invoke(cli, ["--version"])

        assert result.exit_code == 0
        assert "1.0.0" in result.output

    def test_cli_no_command_shows_help(self, runner: CliRunner) -> None:
        """Test that CLI without command shows help."""
        result = runner.invoke(cli, [])

        assert result.exit_code == 0
        assert "Usage:" in result.output

    @patch("ponderous.cli.get_config")
    def test_cli_debug_flag(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test debug flag sets debug mode."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["--debug", "config", "--show"])

        # Should not crash and should pass debug flag
        assert result.exit_code == 0

    @patch("ponderous.cli.get_config")
    def test_cli_verbose_flag(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test verbose flag is handled."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["--verbose", "config", "--show"])

        assert result.exit_code == 0

    @patch("ponderous.cli.PonderousConfig.from_file")
    def test_cli_config_file_option(
        self,
        mock_from_file: Mock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        """Test loading config from file."""
        config_file = tmp_path / "test_config.toml"
        config_file.write_text("[database]\npath = '/test/path'")

        # Create a real config object and then mock from_file to return it
        from ponderous.shared.config import PonderousConfig

        mock_config = PonderousConfig()
        mock_from_file.return_value = mock_config
        # Don't mock get_config since the context creation should use the loaded config

        result = runner.invoke(
            cli, ["--config-file", str(config_file), "config", "--show"]
        )

        mock_from_file.assert_called_once_with(config_file)
        assert result.exit_code == 0

    @patch("ponderous.cli.get_config")
    def test_cli_invalid_config_file(
        self, mock_get_config: Mock, runner: CliRunner
    ) -> None:
        """Test error handling for invalid config file."""
        mock_get_config.return_value = Mock(spec=PonderousConfig)

        result = runner.invoke(cli, ["--config-file", "/nonexistent/config.toml"])

        assert result.exit_code == 2  # Click exits with 2 for bad parameter


class TestUserCommands:
    """Test user management commands."""

    @patch("ponderous.cli.get_config")
    def test_list_users(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test list users command."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["user", "list"])

        assert result.exit_code == 0
        assert "Listing Users" in result.output
        assert "not yet implemented" in result.output

    @patch("ponderous.cli.get_config")
    def test_user_stats(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test user stats command."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["user", "stats", "testuser"])

        assert result.exit_code == 0
        assert "User Statistics for testuser" in result.output
        assert "not yet implemented" in result.output

    @patch("ponderous.cli.get_config")
    def test_user_stats_missing_argument(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test user stats command without user_id argument."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["user", "stats"])

        assert result.exit_code == 2  # Click exits with 2 for missing argument


class TestSyncCollectionCommand:
    """Test collection syncing functionality."""

    @patch("ponderous.cli.CollectionService")
    @patch("ponderous.cli.get_config")
    def test_sync_collection_basic(
        self,
        mock_get_config: Mock,
        mock_collection_service_class: Mock,
        runner: CliRunner,
        mock_config: Mock,
    ) -> None:
        """Test basic collection sync command."""
        mock_get_config.return_value = mock_config

        # Mock the CollectionService instance and its methods
        mock_service = Mock()
        mock_collection_service_class.return_value = mock_service
        mock_service.validate_username_format.return_value = True

        # Mock the async sync_user_collection method with proper types
        mock_response = Mock()
        mock_response.success = True
        mock_response.username = "testuser"
        mock_response.source = "moxfield"
        mock_response.unique_cards = 100
        mock_response.total_cards = 150
        mock_response.items_processed = 250
        mock_response.sync_duration_seconds = 2.5
        mock_service.sync_user_collection = AsyncMock(return_value=mock_response)

        result = runner.invoke(cli, ["sync-collection", "--username", "testuser"])

        assert result.exit_code == 0
        assert "Syncing Collection" in result.output
        assert "testuser" in result.output
        assert "Moxfield" in result.output

    @patch("ponderous.cli.CollectionService")
    @patch("ponderous.cli.get_config")
    def test_sync_collection_with_source(
        self,
        mock_get_config: Mock,
        mock_collection_service_class: Mock,
        runner: CliRunner,
        mock_config: Mock,
    ) -> None:
        """Test collection sync with specified source."""
        mock_get_config.return_value = mock_config

        # Mock the CollectionService instance and its methods
        mock_service = Mock()
        mock_collection_service_class.return_value = mock_service
        mock_service.validate_username_format.return_value = True

        # Mock the async sync_user_collection method with proper types
        mock_response = Mock()
        mock_response.success = True
        mock_response.username = "testuser"
        mock_response.source = "moxfield"
        mock_response.unique_cards = 100
        mock_response.total_cards = 150
        mock_response.items_processed = 250
        mock_response.sync_duration_seconds = 2.5
        mock_service.sync_user_collection = AsyncMock(return_value=mock_response)

        result = runner.invoke(
            cli, ["sync-collection", "--username", "testuser", "--source", "moxfield"]
        )

        assert result.exit_code == 0
        assert "testuser" in result.output
        assert "Moxfield" in result.output

    @patch("ponderous.cli.CollectionService")
    @patch("ponderous.cli.get_config")
    def test_sync_collection_force(
        self,
        mock_get_config: Mock,
        mock_collection_service_class: Mock,
        runner: CliRunner,
        mock_config: Mock,
    ) -> None:
        """Test collection sync with force flag."""
        mock_get_config.return_value = mock_config

        # Mock the CollectionService instance and its methods
        mock_service = Mock()
        mock_collection_service_class.return_value = mock_service
        mock_service.validate_username_format.return_value = True

        # Mock the async sync_user_collection method with proper types
        mock_response = Mock()
        mock_response.success = True
        mock_response.username = "testuser"
        mock_response.source = "moxfield"
        mock_response.unique_cards = 100
        mock_response.total_cards = 150
        mock_response.items_processed = 250
        mock_response.sync_duration_seconds = 2.5
        mock_service.sync_user_collection = AsyncMock(return_value=mock_response)

        result = runner.invoke(
            cli, ["sync-collection", "--username", "testuser", "--force"]
        )

        assert result.exit_code == 0
        assert "Force sync enabled" in result.output

    @patch("ponderous.cli.get_config")
    def test_sync_collection_missing_username(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test sync collection without username."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["sync-collection"])

        assert result.exit_code == 2  # Click exits with 2 for missing required option

    @patch("ponderous.cli.get_config")
    def test_sync_collection_invalid_source(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test sync collection with invalid source."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli, ["sync-collection", "--username", "test", "--source", "invalid"]
        )

        assert result.exit_code == 2  # Click exits with 2 for invalid choice


class TestDiscoverCommandersCommand:
    """Test commander discovery functionality."""

    @patch("ponderous.cli.get_config")
    def test_discover_commanders_basic(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test basic commander discovery."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["discover-commanders", "--user-id", "testuser"])

        assert result.exit_code == 0
        assert "Commander Discovery" in result.output
        assert "testuser" in result.output
        assert "Expected Output Format" in result.output

    @patch("ponderous.cli.get_config")
    def test_discover_commanders_with_filters(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test commander discovery with various filters."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli,
            [
                "discover-commanders",
                "--user-id",
                "testuser",
                "--colors",
                "BG",
                "--budget-max",
                "300",
                "--archetype",
                "combo",
                "--min-completion",
                "0.8",
            ],
        )

        assert result.exit_code == 0
        assert "testuser" in result.output
        assert "Colors: BG" in result.output
        assert "Archetype: combo" in result.output
        assert "Min Completion: 80.0%" in result.output

    @patch("ponderous.cli.get_config")
    def test_discover_commanders_budget_bracket(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test commander discovery with budget bracket."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli,
            ["discover-commanders", "--user-id", "testuser", "--budget-bracket", "mid"],
        )

        assert result.exit_code == 0
        assert "Budget: Mid" in result.output

    @patch("ponderous.cli.get_config")
    def test_discover_commanders_output_formats(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test different output formats."""
        mock_get_config.return_value = mock_config

        for format_type in ["table", "json", "csv"]:
            result = runner.invoke(
                cli,
                [
                    "discover-commanders",
                    "--user-id",
                    "testuser",
                    "--format",
                    format_type,
                ],
            )

            assert result.exit_code == 0

    @patch("ponderous.cli.get_config")
    def test_discover_commanders_missing_user_id(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test discovery without user ID."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["discover-commanders"])

        assert result.exit_code == 2  # Missing required option


class TestQuickDiscoverCommand:
    """Test quick discovery functionality."""

    @patch("ponderous.cli.get_config")
    def test_discover_quick_basic(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test basic quick discovery."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["discover", "--user-id", "testuser"])

        assert result.exit_code == 0
        assert "Quick Commander Discovery" in result.output
        assert "testuser" in result.output

    @patch("ponderous.cli.get_config")
    def test_discover_quick_with_options(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test quick discovery with options."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli,
            [
                "discover",
                "--user-id",
                "testuser",
                "--budget-bracket",
                "high",
                "--min-completion",
                "0.8",
                "--limit",
                "5",
            ],
        )

        assert result.exit_code == 0
        assert "Budget: High" in result.output
        assert "Min Completion: 80.0%" in result.output


class TestRecommendDecksCommand:
    """Test deck recommendation functionality."""

    @patch("ponderous.cli.get_config")
    def test_recommend_decks_basic(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test basic deck recommendations."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli, ["recommend-decks", "Meren of Clan Nel Toth", "--user-id", "testuser"]
        )

        assert result.exit_code == 0
        assert "Deck Recommendations" in result.output
        assert "Meren of Clan Nel Toth" in result.output
        assert "testuser" in result.output

    @patch("ponderous.cli.get_config")
    def test_recommend_decks_with_filters(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test deck recommendations with filters."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli,
            [
                "recommend-decks",
                "Atraxa, Praetors' Voice",
                "--user-id",
                "testuser",
                "--budget",
                "mid",
                "--min-completion",
                "0.8",
                "--sort-by",
                "completion",
                "--limit",
                "5",
            ],
        )

        assert result.exit_code == 0
        assert "Atraxa, Praetors' Voice" in result.output
        assert "Budget Filter: Mid" in result.output
        assert "Min Completion: 80.0%" in result.output
        assert "Sort by: Completion" in result.output

    @patch("ponderous.cli.get_config")
    def test_recommend_decks_missing_arguments(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test deck recommendations with missing arguments."""
        mock_get_config.return_value = mock_config

        # Missing commander name
        result = runner.invoke(cli, ["recommend-decks", "--user-id", "testuser"])
        assert result.exit_code == 2

        # Missing user ID
        result = runner.invoke(cli, ["recommend-decks", "Test Commander"])
        assert result.exit_code == 2


class TestDeckDetailsCommand:
    """Test detailed deck analysis functionality."""

    @patch("ponderous.cli.get_config")
    def test_deck_details_basic(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test basic deck details."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli, ["deck-details", "Meren of Clan Nel Toth", "--user-id", "testuser"]
        )

        assert result.exit_code == 0
        assert "Detailed Deck Analysis" in result.output
        assert "Meren of Clan Nel Toth" in result.output

    @patch("ponderous.cli.get_config")
    def test_deck_details_with_options(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test deck details with all options."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli,
            [
                "deck-details",
                "Test Commander",
                "--user-id",
                "testuser",
                "--archetype",
                "combo",
                "--budget",
                "mid",
                "--show-missing",
            ],
        )

        assert result.exit_code == 0
        assert "Archetype: combo" in result.output
        assert "Budget: mid" in result.output


class TestAnalyzeCollectionCommand:
    """Test collection analysis functionality."""

    @patch("ponderous.cli.get_config")
    def test_analyze_collection_basic(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test basic collection analysis."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["analyze-collection", "--user-id", "testuser"])

        assert result.exit_code == 0
        assert "Collection Analysis" in result.output
        assert "testuser" in result.output

    @patch("ponderous.cli.get_config")
    def test_analyze_collection_with_flags(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test collection analysis with flags."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli,
            [
                "analyze-collection",
                "--user-id",
                "testuser",
                "--show-themes",
                "--show-gaps",
            ],
        )

        assert result.exit_code == 0
        assert "Theme Analysis" in result.output
        assert "Collection Gaps" in result.output


class TestEDHRECCommands:
    """Test EDHREC-related commands."""

    @patch("ponderous.cli.get_config")
    def test_update_edhrec_basic(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test basic EDHREC update."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["update-edhrec"])

        assert result.exit_code == 0
        assert "Updating EDHREC Data" in result.output

    @patch("ponderous.cli.get_config")
    def test_update_edhrec_popular_only(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test EDHREC update with popular only flag."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli, ["update-edhrec", "--popular-only", "--limit", "50"]
        )

        assert result.exit_code == 0
        assert "Popular commanders only" in result.output
        assert "Limit: 50" in result.output

    @patch("ponderous.cli.get_config")
    def test_update_edhrec_with_file(
        self,
        mock_get_config: Mock,
        runner: CliRunner,
        mock_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test EDHREC update with commanders file."""
        mock_get_config.return_value = mock_config

        commanders_file = tmp_path / "commanders.txt"
        commanders_file.write_text("Meren of Clan Nel Toth\nAtraxa, Praetors' Voice")

        result = runner.invoke(
            cli, ["update-edhrec", "--commanders-file", str(commanders_file)]
        )

        assert result.exit_code == 0
        # Check that the commanders file is referenced in the output
        assert "commanders.txt" in result.output

    @patch("ponderous.cli.get_config")
    def test_edhrec_stats(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test EDHREC stats command."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["edhrec-stats", "Meren of Clan Nel Toth"])

        assert result.exit_code == 0
        assert "EDHREC Statistics for Meren of Clan Nel Toth" in result.output


class TestConfigCommand:
    """Test configuration management."""

    @patch("ponderous.cli.get_config")
    def test_config_show(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test showing configuration."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["config", "--show"])

        assert result.exit_code == 0
        assert "Current Configuration" in result.output
        assert "Database:" in result.output
        assert "Moxfield API:" in result.output

    @patch("ponderous.cli.get_config")
    def test_config_init(
        self,
        mock_get_config: Mock,
        runner: CliRunner,
        mock_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test initializing configuration."""
        mock_get_config.return_value = mock_config
        mock_config.config_dir = tmp_path
        mock_config.save_to_file = Mock()

        result = runner.invoke(cli, ["config", "--init"])

        assert result.exit_code == 0
        assert "Initializing configuration" in result.output
        mock_config.save_to_file.assert_called_once()

    @patch("ponderous.cli.get_config")
    def test_config_init_custom_file(
        self,
        mock_get_config: Mock,
        runner: CliRunner,
        mock_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test initializing configuration with custom file."""
        mock_get_config.return_value = mock_config
        mock_config.save_to_file = Mock()

        config_file = tmp_path / "custom_config.toml"
        result = runner.invoke(cli, ["config", "--init", "--file", str(config_file)])

        assert result.exit_code == 0
        mock_config.save_to_file.assert_called_once_with(config_file)

    @patch("ponderous.cli.get_config")
    def test_config_init_failure(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test configuration initialization failure."""
        mock_get_config.return_value = mock_config
        mock_config.save_to_file = Mock(side_effect=Exception("Write failed"))

        result = runner.invoke(cli, ["config", "--init"])

        assert result.exit_code == 1
        assert "Failed to save configuration" in result.output

    @patch("ponderous.cli.get_config")
    def test_config_no_options(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test config command without options."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(cli, ["config"])

        assert result.exit_code == 0
        assert "--show to view current config" in result.output


class TestErrorHandling:
    """Test error handling throughout the CLI."""

    @patch("ponderous.cli.get_config")
    def test_ponderous_error_handling(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test PonderousError handling."""
        mock_get_config.return_value = mock_config

        # Mock a command that raises PonderousError
        with patch("ponderous.cli.console"):
            error = PonderousError("Test error message")

            # This is a bit tricky to test directly, so we'll test the decorator
            from ponderous.cli import handle_exception

            @handle_exception
            def failing_function() -> None:
                raise error

            with patch("click.get_current_context") as mock_context:
                mock_context.return_value.obj.debug = False

                with pytest.raises(SystemExit):
                    failing_function()

    @patch("ponderous.cli.get_config")
    def test_unexpected_error_handling(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test unexpected error handling."""
        mock_get_config.return_value = mock_config

        from ponderous.cli import handle_exception

        @handle_exception
        def failing_function() -> None:
            raise ValueError("Unexpected error")

        with (
            patch("ponderous.cli.console"),
            patch("click.get_current_context") as mock_context,
        ):
            mock_context.return_value.obj.debug = False

            with pytest.raises(SystemExit):
                failing_function()

    @patch("ponderous.cli.get_config")
    def test_debug_mode_exception_details(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test that debug mode shows exception details."""
        mock_get_config.return_value = mock_config

        from ponderous.cli import handle_exception

        @handle_exception
        def failing_function() -> None:
            raise ValueError("Test error")

        with (
            patch("ponderous.cli.console") as mock_console,
            patch("click.get_current_context") as mock_context,
        ):
            mock_context.return_value.obj.debug = True

            with pytest.raises(SystemExit):
                failing_function()

            # Should call print_exception when debug is True
            mock_console.print_exception.assert_called_once()


class TestPonderousContext:
    """Test the PonderousContext class."""

    def test_context_initialization(self) -> None:
        """Test context initialization."""
        with patch("ponderous.cli.get_config") as mock_get_config:
            mock_config = Mock()
            mock_config.debug = True
            mock_get_config.return_value = mock_config

            context = PonderousContext()

            assert context.config == mock_config
            assert context.debug is True
            assert context.verbose is False


class TestImportCollectionCommand:
    """Test collection import functionality."""

    @patch("ponderous.cli.get_config")
    @patch("ponderous.cli.MoxfieldCSVImporter")
    def test_import_collection_validation_only(
        self,
        mock_importer_class: Mock,
        mock_get_config: Mock,
        runner: CliRunner,
        mock_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test collection import validation mode."""
        mock_get_config.return_value = mock_config

        # Create a test CSV file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Count,Name,Edition\n1,Lightning Bolt,Unlimited\n")

        # Mock importer instance and response
        mock_importer = Mock()
        mock_importer_class.return_value = mock_importer
        mock_importer.supports_format.return_value = True

        mock_response = Mock()
        mock_response.success = True
        mock_response.items_processed = 1
        mock_response.items_imported = 0
        mock_response.items_skipped = 0
        mock_response.validation_only = True
        mock_response.processing_time_seconds = 0.01
        mock_response.has_errors = False
        mock_response.has_warnings = False
        mock_importer.import_collection = AsyncMock(return_value=mock_response)

        result = runner.invoke(
            cli,
            [
                "import-collection",
                "--file",
                str(test_csv),
                "--user-id",
                "test_user",
                "--validate-only",
            ],
        )

        assert result.exit_code == 0
        assert "File validation completed!" in result.output
        assert "1 items processed" in result.output
        assert "Validation Summary:" in result.output

    @patch("ponderous.cli.get_config")
    @patch("ponderous.cli.MoxfieldCSVImporter")
    def test_import_collection_full_import(
        self,
        mock_importer_class: Mock,
        mock_get_config: Mock,
        runner: CliRunner,
        mock_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test full collection import."""
        mock_get_config.return_value = mock_config

        # Create a test CSV file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Count,Name,Edition\n2,Sol Ring,Commander 2021\n")

        # Mock importer instance and response
        mock_importer = Mock()
        mock_importer_class.return_value = mock_importer
        mock_importer.supports_format.return_value = True

        mock_response = Mock()
        mock_response.success = True
        mock_response.items_processed = 1
        mock_response.items_imported = 1
        mock_response.items_skipped = 0
        mock_response.validation_only = False
        mock_response.processing_time_seconds = 0.05
        mock_response.has_errors = False
        mock_response.has_warnings = False
        mock_response.success_rate = 100.0
        mock_importer.import_collection = AsyncMock(return_value=mock_response)

        result = runner.invoke(
            cli,
            ["import-collection", "--file", str(test_csv), "--user-id", "test_user"],
        )

        assert result.exit_code == 0
        assert "Collection import completed!" in result.output
        assert "1 items processed" in result.output
        assert "1 items imported" in result.output
        assert "100.0%" in result.output
        assert "Import Summary:" in result.output

    @patch("ponderous.cli.get_config")
    @patch("ponderous.cli.MoxfieldCSVImporter")
    def test_import_collection_with_errors(
        self,
        mock_importer_class: Mock,
        mock_get_config: Mock,
        runner: CliRunner,
        mock_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test collection import with errors."""
        mock_get_config.return_value = mock_config

        # Create a test CSV file
        test_csv = tmp_path / "bad.csv"
        test_csv.write_text("Count,Name\n0,Invalid Card\n")

        # Mock importer instance and response
        mock_importer = Mock()
        mock_importer_class.return_value = mock_importer
        mock_importer.supports_format.return_value = True

        mock_response = Mock()
        mock_response.success = False
        mock_response.items_processed = 0
        mock_response.items_imported = 0
        mock_response.items_skipped = 0
        mock_response.validation_only = False
        mock_response.processing_time_seconds = 0.01
        mock_response.has_errors = True
        mock_response.has_warnings = False
        mock_response.errors = ["Missing required column: Edition"]
        mock_importer.import_collection = AsyncMock(return_value=mock_response)

        result = runner.invoke(
            cli,
            ["import-collection", "--file", str(test_csv), "--user-id", "test_user"],
        )

        assert result.exit_code == 1
        assert "Collection import failed!" in result.output
        assert "Missing required column: Edition" in result.output

    @patch("ponderous.cli.get_config")
    def test_import_collection_missing_file(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test import with missing file."""
        mock_get_config.return_value = mock_config

        result = runner.invoke(
            cli,
            [
                "import-collection",
                "--file",
                "nonexistent.csv",
                "--user-id",
                "test_user",
            ],
        )

        assert result.exit_code == 2  # Click error for invalid path

    @patch("ponderous.cli.get_config")
    def test_import_collection_missing_required_arguments(
        self, mock_get_config: Mock, runner: CliRunner, mock_config: Mock
    ) -> None:
        """Test import with missing required arguments."""
        mock_get_config.return_value = mock_config

        # Missing file
        result = runner.invoke(cli, ["import-collection", "--user-id", "test_user"])
        assert result.exit_code == 2

        # Missing user-id
        result = runner.invoke(cli, ["import-collection", "--file", "test.csv"])
        assert result.exit_code == 2

    @patch("ponderous.cli.get_config")
    @patch("ponderous.cli.MoxfieldCSVImporter")
    def test_import_collection_unsupported_format(
        self,
        mock_importer_class: Mock,
        mock_get_config: Mock,
        runner: CliRunner,
        mock_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test import with unsupported file format."""
        mock_get_config.return_value = mock_config

        # Create a test file with wrong extension
        test_file = tmp_path / "test.txt"
        test_file.write_text("some content")

        # Mock importer to return False for format support
        mock_importer = Mock()
        mock_importer_class.return_value = mock_importer
        mock_importer.supports_format.return_value = False

        result = runner.invoke(
            cli,
            ["import-collection", "--file", str(test_file), "--user-id", "test_user"],
        )

        assert result.exit_code == 1
        assert "File format not supported" in result.output

    @patch("ponderous.cli.get_config")
    @patch("ponderous.cli.MoxfieldCSVImporter")
    def test_import_collection_with_warnings(
        self,
        mock_importer_class: Mock,
        mock_get_config: Mock,
        runner: CliRunner,
        mock_config: Mock,
        tmp_path: Path,
    ) -> None:
        """Test collection import with warnings."""
        mock_get_config.return_value = mock_config

        # Create a test CSV file
        test_csv = tmp_path / "test.csv"
        test_csv.write_text("Count,Name,Edition\n1,Test Card,Test Set\n")

        # Mock importer instance and response
        mock_importer = Mock()
        mock_importer_class.return_value = mock_importer
        mock_importer.supports_format.return_value = True

        mock_response = Mock()
        mock_response.success = True
        mock_response.items_processed = 1
        mock_response.items_imported = 1
        mock_response.items_skipped = 0
        mock_response.validation_only = False
        mock_response.processing_time_seconds = 0.01
        mock_response.has_errors = False
        mock_response.has_warnings = True
        mock_response.warnings = ["Unknown set: Test Set"]
        mock_response.success_rate = 100.0
        mock_importer.import_collection = AsyncMock(return_value=mock_response)

        result = runner.invoke(
            cli,
            ["import-collection", "--file", str(test_csv), "--user-id", "test_user"],
        )

        assert result.exit_code == 0
        assert "Collection import completed!" in result.output
        assert "Warnings:" in result.output
        assert "Unknown set: Test Set" in result.output


class TestMainFunction:
    """Test the main entry point function."""

    @patch("ponderous.cli.cli")
    def test_main_function(self, mock_cli: Mock) -> None:
        """Test main function calls cli."""
        from ponderous.cli import main

        main()

        mock_cli.assert_called_once()
