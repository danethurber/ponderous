"""
Tests for commander discovery commands.

Tests commander discovery functionality with filtering options
and recommendation generation.
"""

from unittest.mock import Mock, patch

from click.testing import CliRunner

from ..base_test import BaseCLITest, DatabaseCommandTest
from ..helpers.mocks import MockRepositoryFactory


class TestDiscoverCommandersCommand(DatabaseCommandTest):
    """Test commander discovery functionality."""

    def test_discover_commanders_help(self, cli_runner: CliRunner) -> None:
        """Test discover-commanders command help display."""
        result = self.invoke_cli(["discover-commanders", "--help"])
        self.assert_success(result)
        self.assert_help_displayed(result, "discover-commanders")
        assert "Discover optimal commanders" in result.output

    def test_discover_commanders_missing_user_id(self, cli_runner: CliRunner) -> None:
        """Test discover command with missing user-id."""
        result = self.invoke_cli(["discover-commanders"])
        self.assert_failure(
            result, expected_exit_code=2, expected_error="Missing option"
        )

    def test_discover_commanders_basic(self, cli_runner: CliRunner) -> None:
        """Test that discover-commanders accepts valid arguments."""
        result = self.invoke_cli(["discover-commanders", "--user-id", "testuser"])

        # Test CLI accepts arguments (business logic tested at integration level)
        assert "testuser" in result.output
        assert "Commander Discovery" in result.output

    def test_discover_commanders_with_filters(self, cli_runner: CliRunner) -> None:
        """Test that discover-commanders accepts filtering options."""
        result = self.invoke_cli(
            [
                "discover-commanders",
                "--user-id",
                "testuser",
                "--colors",
                "BG",
                "--budget-max",
                "300",
                "--min-completion",
                "0.8",
                "--limit",
                "5",
            ]
        )

        # Test CLI accepts all filter options
        assert "testuser" in result.output
        assert "Colors: BG" in result.output

    @patch("ponderous.infrastructure.database.CommanderRepositoryImpl")
    def test_discover_commanders_budget_bracket(
        self, mock_repo_class: Mock, sample_commander_recommendations: list
    ) -> None:
        """Test commander discovery with budget bracket filter."""
        mock_repo = MockRepositoryFactory.create_commander_repository()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_recommendations_for_collection.return_value = (
            sample_commander_recommendations
        )

        result = self.invoke_cli(
            ["discover-commanders", "--user-id", "testuser", "--budget-bracket", "mid"]
        )

        self.assert_success(result)
        assert "Budget: Mid" in result.output

    @patch("ponderous.infrastructure.database.CommanderRepositoryImpl")
    def test_discover_commanders_no_results(self, mock_repo_class: Mock) -> None:
        """Test commander discovery with no matching results."""
        mock_repo = MockRepositoryFactory.create_commander_repository()
        mock_repo_class.return_value = mock_repo
        mock_repo.get_recommendations_for_collection.return_value = []

        result = self.invoke_cli(["discover-commanders", "--user-id", "testuser"])

        self.assert_success(result)
        assert "No commanders found matching criteria" in result.output
        assert "Try lowering --min-completion" in result.output

    def test_discover_commanders_output_formats(self, cli_runner: CliRunner) -> None:
        """Test that discover-commanders accepts format options."""
        # Test JSON format option
        result = self.invoke_cli(
            ["discover-commanders", "--user-id", "testuser", "--format", "json"]
        )

        # Test CLI accepts format option
        assert "testuser" in result.output


class TestQuickDiscoverCommand(BaseCLITest):
    """Test quick discovery functionality."""

    def test_discover_quick_help(self, cli_runner: CliRunner) -> None:
        """Test discover command help display."""
        result = self.invoke_cli(["discover", "--help"])
        self.assert_success(result)
        self.assert_help_displayed(result, "discover")
        assert "Quick commander discovery" in result.output

    def test_discover_quick_missing_user_id(self, cli_runner: CliRunner) -> None:
        """Test quick discover with missing user-id."""
        result = self.invoke_cli(["discover"])
        self.assert_failure(
            result, expected_exit_code=2, expected_error="Missing option"
        )

    def test_discover_quick_basic(self, cli_runner: CliRunner) -> None:
        """Test basic quick discovery."""
        result = self.invoke_cli(["discover", "--user-id", "testuser"])

        self.assert_success(result)
        assert "testuser" in result.output
        assert "Quick discovery not yet implemented" in result.output

    def test_discover_quick_with_options(self, cli_runner: CliRunner) -> None:
        """Test quick discovery with options."""
        result = self.invoke_cli(
            [
                "discover",
                "--user-id",
                "testuser",
                "--budget-bracket",
                "high",
                "--min-completion",
                "0.75",
                "--limit",
                "5",
            ]
        )

        self.assert_success(result)
        assert "testuser" in result.output
        assert "Budget: High" in result.output
        assert "Min Completion: 75.0%" in result.output
