"""
Tests for table formatters.

Tests table formatting functionality for collection summaries,
commander recommendations, and import results.
"""

from io import StringIO
from unittest.mock import Mock

import pytest
from rich.console import Console

from ponderous.presentation.formatters.table import (
    CollectionSummaryFormatter,
    CommanderRecommendationFormatter,
    ImportSummaryFormatter,
)


class TestCollectionSummaryFormatter:
    """Test collection summary table formatting."""

    @pytest.fixture
    def formatter(self) -> CollectionSummaryFormatter:
        """Create formatter with mock console."""
        console = Console(file=StringIO(), width=80)
        return CollectionSummaryFormatter(console)

    def test_format_basic_summary(
        self, formatter: CollectionSummaryFormatter, sample_collection_data: dict
    ) -> None:
        """Test basic collection summary formatting."""
        formatter.format(sample_collection_data)

        output = formatter.console.file.getvalue()

        # Verify key data is present
        assert "Total Cards" in output
        assert "1250" in output  # total_cards value
        assert "Unique Cards" in output
        assert "875" in output  # unique_cards value
        assert "Sets Represented" in output
        assert "45" in output  # sets_represented value

    def test_format_with_last_import(
        self, formatter: CollectionSummaryFormatter
    ) -> None:
        """Test formatting with last import timestamp."""
        data = {
            "total_cards": 500,
            "unique_cards": 400,
            "sets_represented": 20,
            "foil_cards": 50,
            "last_import": "2024-01-15 10:30:00",
        }

        formatter.format(data)
        output = formatter.console.file.getvalue()

        assert "Last Import" in output
        assert "2024-01-15 10:30:00" in output

    def test_format_without_last_import(
        self, formatter: CollectionSummaryFormatter
    ) -> None:
        """Test formatting without last import timestamp."""
        data = {
            "total_cards": 500,
            "unique_cards": 400,
            "sets_represented": 20,
            "foil_cards": 50,
        }

        formatter.format(data)
        output = formatter.console.file.getvalue()

        assert "Last Import" not in output


class TestCommanderRecommendationFormatter:
    """Test commander recommendation table formatting."""

    @pytest.fixture
    def formatter(self) -> CommanderRecommendationFormatter:
        """Create formatter with mock console."""
        console = Console(file=StringIO(), width=120)
        return CommanderRecommendationFormatter(console)

    def test_format_recommendations(
        self,
        formatter: CommanderRecommendationFormatter,
        sample_commander_recommendations: list,
    ) -> None:
        """Test basic formatting functionality."""
        # Test that formatter can process data without error
        formatter.format(sample_commander_recommendations)
        output = formatter.console.file.getvalue()

        # Basic validation that table was created
        assert "Commander" in output
        assert len(output) > 0

    def test_format_empty_recommendations(
        self, formatter: CommanderRecommendationFormatter
    ) -> None:
        """Test formatting with empty recommendations list."""
        formatter.format([])

        output = formatter.console.file.getvalue()

        # Should still create table structure
        assert "Rank" in output
        assert "Commander" in output

    def test_format_colorless_commander(
        self, formatter: CommanderRecommendationFormatter
    ) -> None:
        """Test formatting handles edge cases."""
        colorless_rec = {
            "commander_name": "Kozilek, Butcher of Truth",
            "color_identity": [],
            "completion_percentage": 0.90,
            "owned_cards": 72,
            "total_cards": 80,
            "missing_cards_value": 85.50,
            "power_level": 9.1,
        }

        # Test that formatter handles colorless commanders without error
        formatter.format([colorless_rec])
        output = formatter.console.file.getvalue()

        assert "Kozilek" in output
        assert len(output) > 0


class TestImportSummaryFormatter:
    """Test import summary table formatting."""

    @pytest.fixture
    def formatter(self) -> ImportSummaryFormatter:
        """Create formatter with mock console."""
        console = Console(file=StringIO(), width=80)
        return ImportSummaryFormatter(console)

    def test_format_basic_data(self, formatter: ImportSummaryFormatter) -> None:
        """Test basic format method (for abstract compatibility)."""
        formatter.format("test data")

        output = formatter.console.file.getvalue()
        assert "Import summary: test data" in output

    def test_format_import_result_success(
        self, formatter: ImportSummaryFormatter, mock_import_response: Mock
    ) -> None:
        """Test formatting successful import result."""
        formatter.format_import_result(
            mock_import_response,
            "collection.csv",
            "testuser",
            "moxfield_csv",
            validate_only=False,
        )

        output = formatter.console.file.getvalue()

        # Verify summary content
        assert "Import Summary:" in output
        assert "collection.csv" in output
        assert "testuser" in output
        assert "Moxfield_Csv" in output
        assert "500" in output  # items_processed
        assert "485" in output  # items_imported
        assert "15" in output  # items_skipped
        assert "97.0%" in output  # success_rate

    def test_format_import_result_validation_only(
        self, formatter: ImportSummaryFormatter, mock_import_response: Mock
    ) -> None:
        """Test formatting validation-only result."""
        formatter.format_import_result(
            mock_import_response,
            "collection.csv",
            "testuser",
            "moxfield_csv",
            validate_only=True,
        )

        output = formatter.console.file.getvalue()

        assert "Validation Summary:" in output
        assert "Items Imported" not in output  # Should not show import stats
        assert "Items Skipped" not in output
        assert "Success Rate" not in output

    def test_format_import_result_with_timing(
        self, formatter: ImportSummaryFormatter
    ) -> None:
        """Test formatting with processing time."""
        response = Mock()
        response.items_processed = 100
        response.items_imported = 95
        response.items_skipped = 5
        response.success_rate = 95.0
        response.processing_time_seconds = 2.75

        formatter.format_import_result(
            response, "test.csv", "user", "format", validate_only=False
        )

        output = formatter.console.file.getvalue()
        assert "2.75s" in output

    def test_format_import_result_without_timing(
        self, formatter: ImportSummaryFormatter
    ) -> None:
        """Test formatting without processing time."""
        response = Mock()
        response.items_processed = 100
        response.items_imported = 95
        response.items_skipped = 5
        response.success_rate = 95.0
        response.processing_time_seconds = None

        formatter.format_import_result(
            response, "test.csv", "user", "format", validate_only=False
        )

        output = formatter.console.file.getvalue()

        # Should not contain processing time
        assert "Processing Time" not in output
