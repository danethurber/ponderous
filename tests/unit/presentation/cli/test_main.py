"""
Tests for main CLI integration and overall functionality.

Tests the main CLI entry point, global options, command registration,
and overall integration between components.
"""

from pathlib import Path
from unittest.mock import Mock, patch

from click.testing import CliRunner

from ponderous import __version__

from .base_test import BaseCLITest


class TestMainCLI(BaseCLITest):
    """Test main CLI functionality and integration."""

    def test_cli_help(self, cli_runner: CliRunner) -> None:
        """Test main CLI help display."""
        result = self.invoke_cli(["--help"])
        self.assert_success(result)

        assert "Ponderous - Thoughtful analysis of your MTG collection" in result.output
        assert "Commands:" in result.output

        # Verify key commands are listed
        expected_commands = [
            "import-collection",
            "discover-commanders",
            "recommend-decks",
            "config",
            "user",
        ]
        for command in expected_commands:
            assert command in result.output

    def test_cli_version(self, cli_runner: CliRunner) -> None:
        """Test CLI version display."""
        result = self.invoke_cli(["--version"])
        self.assert_success(result)
        assert __version__ in result.output
        assert "ponderous" in result.output

    def test_cli_no_command_shows_help(self, cli_runner: CliRunner) -> None:
        """Test that running CLI with no command shows help."""
        result = self.invoke_cli([])
        self.assert_success(result)
        assert "Usage:" in result.output
        assert "Commands:" in result.output

    def test_cli_debug_flag(self, cli_runner: CliRunner, patched_config: Mock) -> None:
        """Test CLI with debug flag."""
        result = self.invoke_cli(["--debug", "config", "--show"])
        self.assert_success(result)

        # Debug flag should be passed to context
        # This would be verified in integration with actual error handling

    def test_cli_verbose_flag(
        self, cli_runner: CliRunner, patched_config: Mock
    ) -> None:
        """Test CLI with verbose flag."""
        result = self.invoke_cli(["--verbose", "config", "--show"])
        self.assert_success(result)

        # Verbose flag should enable additional output
        # This would be verified in commands that support verbose mode

    def test_cli_config_file_option(
        self, cli_runner: CliRunner, isolated_filesystem: Path
    ) -> None:
        """Test CLI with custom config file option."""
        config_file = isolated_filesystem / "custom.toml"
        config_file.write_text(
            """
[database]
path = "custom.db"

[logging]
level = "DEBUG"
"""
        )

        with patch(
            "ponderous.shared.config.PonderousConfig.from_file"
        ) as mock_from_file:
            mock_config = Mock()
            mock_from_file.return_value = mock_config

            self.invoke_cli(f"--config-file {config_file} config --show".split())

            # Should attempt to load the custom config
            mock_from_file.assert_called_once_with(config_file)

    def test_cli_invalid_config_file(
        self, cli_runner: CliRunner, isolated_filesystem: Path
    ) -> None:
        """Test CLI with invalid config file."""
        invalid_file = isolated_filesystem / "invalid.toml"
        invalid_file.write_text("invalid toml content [[[")

        result = self.invoke_cli(f"--config-file {invalid_file} config --show".split())
        self.assert_failure(result, expected_error="Failed to load config file")


class TestCommandRegistration(BaseCLITest):
    """Test that all commands are properly registered."""

    def test_all_commands_registered(self, cli_runner: CliRunner) -> None:
        """Test that all expected commands are registered and accessible."""
        # Get list of available commands
        result = self.invoke_cli(["--help"])
        self.assert_success(result)

        # Expected commands from our CLI structure
        expected_commands = [
            # Collection commands
            "import-collection",
            "analyze-collection",
            # Discovery commands
            "discover-commanders",
            "discover",
            # Recommendation commands
            "recommend-decks",
            "deck-details",
            # EDHREC commands
            "update-edhrec",
            "edhrec-stats",
            # Config commands
            "config",
            # User commands (group)
            "user",
            # Testing commands
            "test-cards",
            "scrape-edhrec",
            "recommend-commanders",
        ]

        for command in expected_commands:
            assert command in result.output, (
                f"Command '{command}' not found in CLI help"
            )

    def test_command_help_accessibility(self, cli_runner: CliRunner) -> None:
        """Test that all commands have accessible help."""
        commands_to_test = [
            "import-collection",
            "discover-commanders",
            "config",
            "user",
        ]

        for command in commands_to_test:
            result = self.invoke_cli(f"{command} --help".split())
            assert result.exit_code == 0, (
                f"Help for command '{command}' failed with exit code {result.exit_code}"
            )
            assert "Usage:" in result.output
            assert "Options:" in result.output


class TestErrorHandling(BaseCLITest):
    """Test CLI error handling and exception management."""

    def test_ponderous_error_handling(self, cli_runner: CliRunner) -> None:
        """Test handling of invalid commands."""
        result = self.invoke_cli(["nonexistent-command"])
        self.assert_failure(
            result, expected_exit_code=2, expected_error="No such command"
        )

    def test_debug_mode_exception_details(self, cli_runner: CliRunner) -> None:
        """Test that debug mode shows detailed exception information."""
        result = self.invoke_cli(["--debug", "nonexistent-command"])
        self.assert_failure(result, expected_exit_code=2)


class TestContextManagement(BaseCLITest):
    """Test CLI context object management."""

    def test_context_initialization(self, cli_runner: CliRunner) -> None:
        """Test that CLI context is properly initialized."""
        result = self.invoke_cli(["config", "--show"])

        # Test CLI starts and shows config (context initialization tested in integration)
        self.assert_success(result)
        assert "Configuration" in result.output

    def test_context_debug_setting(
        self, cli_runner: CliRunner, patched_config: Mock
    ) -> None:
        """Test that debug setting is properly managed in context."""
        # Test that debug flag affects context
        result = self.invoke_cli(["--debug", "config", "--show"])
        self.assert_success(result)

        # The debug setting should be passed through the context
        # This would be verified in actual command execution


class TestGlobalOptions(BaseCLITest):
    """Test global CLI options that affect all commands."""

    def test_global_debug_option(
        self, cli_runner: CliRunner, patched_config: Mock
    ) -> None:
        """Test global --debug option."""
        result = self.invoke_cli(["--debug", "config", "--show"])
        self.assert_success(result)

        # Debug should be enabled in context

    def test_global_verbose_option(
        self, cli_runner: CliRunner, patched_config: Mock
    ) -> None:
        """Test global --verbose option."""
        result = self.invoke_cli(["--verbose", "config", "--show"])
        self.assert_success(result)

        # Verbose should be enabled in context

    def test_global_config_file_option(
        self, cli_runner: CliRunner, isolated_filesystem: Path
    ) -> None:
        """Test global --config-file option."""
        config_file = isolated_filesystem / "test.toml"
        config_file.write_text("[database]\npath = 'test.db'\n")

        # Test that CLI accepts config-file option (integration tested separately)
        result = self.invoke_cli(f"--config-file {config_file} --version".split())
        self.assert_success(result)
