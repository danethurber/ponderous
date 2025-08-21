"""
Tests for configuration management commands.

Tests the config command functionality including showing current
configuration and initializing new configuration files.
"""

from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from ponderous.shared.config import PonderousConfig

from ..base_test import BaseCLITest, CLIAssertions


class TestConfigCommand(BaseCLITest):
    """Test configuration management command."""

    def test_config_help(self, cli_runner: CliRunner) -> None:
        """Test config command help display."""
        result = self.invoke_cli(["config", "--help"])
        self.assert_success(result)
        self.assert_help_displayed(result, "config")
        assert "Manage Ponderous configuration" in result.output

    def test_config_show(self, cli_runner: CliRunner, patched_config: Mock) -> None:
        """Test displaying current configuration."""
        # Set up mock config with all required attributes
        patched_config.database.path = "/test/ponderous.db"
        patched_config.database.memory = False
        patched_config.database.threads = 4
        patched_config.moxfield.base_url = "https://api2.moxfield.com/v2"
        patched_config.moxfield.timeout = 30.0
        patched_config.moxfield.rate_limit = 2.0
        patched_config.edhrec.base_url = "https://edhrec.com"
        patched_config.edhrec.timeout = 30.0
        patched_config.edhrec.rate_limit = 1.5
        patched_config.analysis.min_completion_threshold = 0.7
        patched_config.analysis.max_commanders_to_analyze = 1000
        patched_config.analysis.cache_results = True
        patched_config.logging.level = "INFO"
        patched_config.logging.file_path = None
        patched_config.debug = False
        patched_config.config_dir = Path("/test/.ponderous")

        result = self.invoke_cli(["config", "--show"])
        self.assert_success(result)

        # Verify configuration sections are displayed
        expected_sections = [
            "Database:",
            "Moxfield API:",
            "EDHREC Scraping:",
            "Analysis:",
            "Logging:",
            "Application:",
        ]
        CLIAssertions.assert_config_panel(result, expected_sections)

        # Verify specific config values
        assert "/test/ponderous.db" in result.output
        assert "https://api2.moxfield.com/v2" in result.output
        assert "INFO" in result.output

    def test_config_init_default(
        self, cli_runner: CliRunner, patched_config: Mock, isolated_filesystem: Path
    ) -> None:
        """Test initializing configuration with default path."""
        patched_config.config_dir = isolated_filesystem / ".ponderous"
        patched_config.save_to_file = Mock()

        result = self.invoke_cli(["config", "--init"])
        self.assert_success(result)

        # Verify save_to_file was called with default path
        expected_path = isolated_filesystem / ".ponderous" / "config.toml"
        patched_config.save_to_file.assert_called_once_with(expected_path)

        assert "Configuration saved" in result.output

    def test_config_init_custom_file(
        self, cli_runner: CliRunner, patched_config: Mock, isolated_filesystem: Path
    ) -> None:
        """Test initializing configuration with custom file path."""
        custom_path = isolated_filesystem / "custom_config.toml"
        patched_config.save_to_file = Mock()

        result = self.invoke_cli(["config", "--init", "--file", str(custom_path)])
        self.assert_success(result)

        # Verify save_to_file was called with custom path
        patched_config.save_to_file.assert_called_once_with(custom_path)

        assert "Configuration saved" in result.output
        # Check for the path in the output (may have line breaks)
        path_str = str(custom_path)
        assert path_str in result.output.replace("\n", "")

    def test_config_init_failure(
        self, cli_runner: CliRunner, patched_config: Mock
    ) -> None:
        """Test configuration initialization failure handling."""
        patched_config.config_dir = Path("/nonexistent")
        patched_config.save_to_file = Mock(
            side_effect=PermissionError("Permission denied")
        )

        result = self.invoke_cli(["config", "--init"])
        self.assert_failure(result, expected_error="Failed to save configuration")

        # Check for error formatting - the actual output is "✗ Failed to save configuration: ..."
        assert "Failed to save configuration" in result.output

    def test_config_no_options(self, cli_runner: CliRunner) -> None:
        """Test config command with no options shows usage help."""
        result = self.invoke_cli(["config"])
        self.assert_success(result)

        assert "Use --show to view current config" in result.output
        assert "or --init to create default config file" in result.output

    @patch("ponderous.shared.config.PonderousConfig.from_file")
    def test_config_file_loading(
        self, mock_from_file: Mock, cli_runner: CliRunner, isolated_filesystem: Path
    ) -> None:
        """Test loading configuration from custom file."""
        config_file = isolated_filesystem / "test_config.toml"
        config_file.write_text("[database]\npath = 'custom.db'\n")

        # Create a mock config with nested attributes
        mock_config = Mock(spec=PonderousConfig)
        mock_config.debug = False

        # Set up nested mock objects like in conftest.py
        mock_config.database = Mock()
        mock_config.database.path = "custom.db"
        mock_config.database.memory = False
        mock_config.database.threads = 4

        mock_config.moxfield = Mock()
        mock_config.moxfield.base_url = "https://api2.moxfield.com/v2"
        mock_config.moxfield.timeout = 30.0
        mock_config.moxfield.rate_limit = 2.0

        mock_config.edhrec = Mock()
        mock_config.edhrec.base_url = "https://edhrec.com"
        mock_config.edhrec.timeout = 30.0
        mock_config.edhrec.rate_limit = 1.5

        mock_config.analysis = Mock()
        mock_config.analysis.min_completion_threshold = 0.7
        mock_config.analysis.max_commanders_to_analyze = 1000
        mock_config.analysis.cache_results = True

        mock_config.logging = Mock()
        mock_config.logging.level = "INFO"
        mock_config.logging.file_path = None

        mock_config.config_dir = isolated_filesystem

        mock_from_file.return_value = mock_config

        result = self.invoke_cli(
            ["--config-file", str(config_file), "config", "--show"]
        )

        # Should succeed and use the custom config
        assert result.exit_code == 0
        mock_from_file.assert_called_once_with(config_file)

    def test_invalid_config_file(
        self, cli_runner: CliRunner, isolated_filesystem: Path
    ) -> None:
        """Test handling of invalid configuration file."""
        invalid_file = isolated_filesystem / "invalid.toml"
        invalid_file.write_text("invalid toml content [[[")

        result = self.invoke_cli(
            ["--config-file", str(invalid_file), "config", "--show"]
        )
        self.assert_failure(result, expected_error="Failed to load config file")
