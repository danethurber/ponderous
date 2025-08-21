"""
Base test classes for CLI testing.

Provides foundational test classes with common functionality
and utilities that can be extended by specific command tests.
"""

from pathlib import Path
from typing import Any
from unittest.mock import Mock

import pytest
from click.testing import CliRunner, Result

from ponderous.presentation.cli.main import cli


class BaseCLITest:
    """Base class for all CLI tests with common utilities."""

    def setup_method(self) -> None:
        """Set up each test method."""
        self.cli_runner = CliRunner()

    def invoke_cli(self, args: list[str], **kwargs: Any) -> Result:
        """Invoke CLI command with error handling."""
        return self.cli_runner.invoke(cli, args, **kwargs)

    def assert_success(
        self, result: Result, expected_patterns: list[str] | None = None
    ) -> None:
        """Assert command succeeded and optionally check output patterns."""
        if result.exit_code != 0:
            pytest.fail(
                f"Command failed with exit code {result.exit_code}:\n{result.output}"
            )

        if expected_patterns:
            for pattern in expected_patterns:
                assert pattern in result.output, (
                    f"Expected pattern '{pattern}' not found in output:\n{result.output}"
                )

    def assert_failure(
        self,
        result: Result,
        expected_exit_code: int = 1,
        expected_error: str | None = None,
    ) -> None:
        """Assert command failed with expected exit code and error message."""
        assert result.exit_code == expected_exit_code, (
            f"Expected exit code {expected_exit_code}, got {result.exit_code}"
        )

        if expected_error:
            assert expected_error in result.output, (
                f"Expected error '{expected_error}' not found in output:\n{result.output}"
            )

    def assert_help_displayed(
        self, result: Result, command_name: str | None = None
    ) -> None:
        """Assert that help text is displayed."""
        assert "Usage:" in result.output
        assert "Options:" in result.output
        if command_name:
            assert command_name in result.output


class CommandTestMixin:
    """Mixin providing standard command testing patterns."""

    def test_command_help(self, cli_runner: CliRunner, command_name: str) -> None:
        """Test that command shows help with --help flag."""
        result = cli_runner.invoke(cli, [command_name, "--help"])
        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "Options:" in result.output

    def test_command_missing_required_args(
        self, cli_runner: CliRunner, command_name: str, expected_error: str
    ) -> None:
        """Test command behavior with missing required arguments."""
        result = cli_runner.invoke(cli, [command_name])
        assert result.exit_code != 0
        assert expected_error in result.output


class DatabaseCommandTest(BaseCLITest):
    """Base class for commands that interact with the database."""

    @pytest.fixture(autouse=True)
    def setup_database_mocks(
        self, patched_db_connection: Mock, mock_repositories: dict[str, Mock]
    ) -> None:
        """Automatically set up database mocks for each test."""
        self.mock_db = patched_db_connection
        self.mock_repos = mock_repositories


class AsyncCommandTest(BaseCLITest):
    """Base class for commands that use async operations."""

    @pytest.fixture(autouse=True)
    def setup_async_mocks(self) -> None:
        """Set up common async mocks."""
        # These will be patched in individual test classes as needed
        pass


class FileCommandTest(BaseCLITest):
    """Base class for commands that work with files."""

    @pytest.fixture(autouse=True)
    def setup_file_mocks(self, isolated_filesystem: Path) -> None:
        """Set up isolated filesystem for file operations."""
        self.test_dir = isolated_filesystem
        self.create_test_files()

    def create_test_files(self) -> None:
        """Create test files that can be used across file-based tests."""
        # Create a sample CSV file with correct Moxfield headers
        self.sample_csv = self.test_dir / "sample_collection.csv"
        self.sample_csv.write_text(
            "Name,Edition,Collector Number,Foil,Count\n"
            "Lightning Bolt,LEA,1,false,1\n"
            "Sol Ring,LEA,2,false,1\n"
            "Black Lotus,LEA,3,true,1\n"
        )

        # Create a sample config file
        self.sample_config = self.test_dir / "config.toml"
        self.sample_config.write_text(
            '[database]\npath = "test.db"\n\n[logging]\nlevel = "DEBUG"\n'
        )


class CLIAssertions:
    """Custom assertion helpers for CLI testing."""

    @staticmethod
    def assert_table_output(
        result: Result, expected_columns: list[str], min_rows: int = 1
    ) -> None:
        """Assert that output contains a table with expected structure."""
        output_lines = result.output.split("\n")

        # Look for table headers
        header_found = False
        for line in output_lines:
            if all(col in line for col in expected_columns):
                header_found = True
                break

        assert header_found, (
            f"Table with columns {expected_columns} not found in output:\n{result.output}"
        )

        # Count data rows (rough estimate)
        data_rows = [
            line
            for line in output_lines
            if line.strip() and "│" in line and not line.startswith("╭")
        ]
        assert len(data_rows) >= min_rows, (
            f"Expected at least {min_rows} data rows, found {len(data_rows)}"
        )

    @staticmethod
    def assert_progress_indicators(result: Result) -> None:
        """Assert that output contains progress indicators."""
        progress_patterns = ["🎉", "📊", "📥", "⏱️", "✅", "⚠️", "❌"]
        found_indicators = [
            pattern for pattern in progress_patterns if pattern in result.output
        ]
        assert found_indicators, (
            f"No progress indicators found in output:\n{result.output}"
        )

    @staticmethod
    def assert_config_panel(result: Result, expected_sections: list[str]) -> None:
        """Assert that configuration panel contains expected sections."""
        assert "Configuration" in result.output
        for section in expected_sections:
            assert section in result.output, (
                f"Config section '{section}' not found in output:\n{result.output}"
            )

    @staticmethod
    def assert_error_formatting(result: Result, error_type: str = "Error") -> None:
        """Assert that errors are properly formatted with styling."""
        assert (
            f"[red]{error_type}:[/red]" in result.output or error_type in result.output
        )
