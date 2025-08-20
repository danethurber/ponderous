"""Tests for Moxfield CSV importer."""

from pathlib import Path

import pytest

from ponderous.infrastructure.database import DatabaseConnection
from ponderous.infrastructure.importers import (
    ImportFileError,
    ImportRequest,
    ImportValidationError,
    MoxfieldCSVImporter,
)
from ponderous.shared.config import DatabaseConfig


class TestMoxfieldCSVImporter:
    """Test cases for MoxfieldCSVImporter."""

    @pytest.fixture
    def importer(self) -> MoxfieldCSVImporter:
        """Create importer instance with in-memory database."""
        # Create in-memory database for testing
        config = DatabaseConfig(memory=True, threads=1)
        db_connection = DatabaseConnection(config)
        return MoxfieldCSVImporter(db_connection)

    @pytest.fixture
    def fixtures_dir(self) -> Path:
        """Get path to test fixtures directory."""
        return Path(__file__).parent.parent.parent.parent / "fixtures" / "csv"

    @pytest.fixture
    def valid_minimal_csv(self, fixtures_dir: Path) -> Path:
        """Path to valid minimal CSV fixture."""
        return fixtures_dir / "moxfield_valid_minimal.csv"

    @pytest.fixture
    def valid_complete_csv(self, fixtures_dir: Path) -> Path:
        """Path to valid complete CSV fixture."""
        return fixtures_dir / "moxfield_valid_complete.csv"

    @pytest.fixture
    def invalid_missing_required_csv(self, fixtures_dir: Path) -> Path:
        """Path to invalid CSV missing required columns."""
        return fixtures_dir / "moxfield_invalid_missing_required.csv"

    @pytest.fixture
    def invalid_bad_data_csv(self, fixtures_dir: Path) -> Path:
        """Path to invalid CSV with bad data."""
        return fixtures_dir / "moxfield_invalid_bad_data.csv"

    @pytest.fixture
    def edge_cases_csv(self, fixtures_dir: Path) -> Path:
        """Path to edge cases CSV fixture."""
        return fixtures_dir / "moxfield_edge_cases.csv"

    def test_supported_formats(self, importer: MoxfieldCSVImporter) -> None:
        """Test supported file formats."""
        assert ".csv" in importer.supported_formats

    def test_source_name(self, importer: MoxfieldCSVImporter) -> None:
        """Test source name."""
        assert importer.source_name == "moxfield_csv"

    def test_supports_format_csv(self, importer: MoxfieldCSVImporter) -> None:
        """Test CSV format support."""
        csv_path = Path("test.csv")
        assert importer.supports_format(csv_path)

    def test_supports_format_case_insensitive(
        self, importer: MoxfieldCSVImporter
    ) -> None:
        """Test case insensitive format support."""
        csv_path = Path("test.CSV")
        assert importer.supports_format(csv_path)

    def test_supports_format_unsupported(self, importer: MoxfieldCSVImporter) -> None:
        """Test unsupported format."""
        txt_path = Path("test.txt")
        assert not importer.supports_format(txt_path)

    @pytest.mark.asyncio
    async def test_parse_items_valid_minimal(
        self, importer: MoxfieldCSVImporter, valid_minimal_csv: Path
    ) -> None:
        """Test parsing valid minimal CSV."""
        items = await importer.parse_items(valid_minimal_csv, "test_user")

        assert len(items) == 3

        # Check first item
        assert items[0].user_id == "test_user"
        assert items[0].card_name == "Lightning Bolt"
        assert items[0].quantity == 1
        assert items[0].foil_quantity == 0

        # Check second item
        assert items[1].card_name == "Sol Ring"
        assert items[1].quantity == 2

    @pytest.mark.asyncio
    async def test_parse_items_valid_complete(
        self, importer: MoxfieldCSVImporter, valid_complete_csv: Path
    ) -> None:
        """Test parsing valid complete CSV with all fields."""
        items = await importer.parse_items(valid_complete_csv, "test_user")

        assert len(items) == 5

        # Check foil handling
        sol_ring = next(item for item in items if item.card_name == "Sol Ring")
        assert sol_ring.foil_quantity == 2
        assert sol_ring.quantity == 0  # All copies are foil

        # Check etched foil handling
        mox_diamond = next(item for item in items if item.card_name == "Mox Diamond")
        assert mox_diamond.foil_quantity == 1
        assert mox_diamond.quantity == 0  # Etched counts as foil

    @pytest.mark.asyncio
    async def test_parse_items_edge_cases(
        self, importer: MoxfieldCSVImporter, edge_cases_csv: Path
    ) -> None:
        """Test parsing CSV with edge cases."""
        items = await importer.parse_items(edge_cases_csv, "test_user")

        assert len(items) == 4

        # Check comma handling
        comma_card = next(item for item in items if "comma" in item.card_name)
        assert comma_card.card_name == "Card with, comma"

        # Check quotes handling
        quotes_card = next(item for item in items if "quotes" in item.card_name)
        assert quotes_card.card_name == 'Card with "quotes"'
        assert quotes_card.foil_quantity == 1  # "FOIL" should be case-insensitive

        # Check large quantities
        bulk_card = next(item for item in items if item.card_name == "Bulk Common")
        assert bulk_card.quantity == 100

    @pytest.mark.asyncio
    async def test_parse_items_missing_required_columns(
        self, importer: MoxfieldCSVImporter, invalid_missing_required_csv: Path
    ) -> None:
        """Test error on missing required columns."""
        with pytest.raises(ImportValidationError) as exc_info:
            await importer.parse_items(invalid_missing_required_csv, "test_user")

        assert "required column" in str(exc_info.value).lower()
        assert "edition" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_parse_items_invalid_data(
        self, importer: MoxfieldCSVImporter, invalid_bad_data_csv: Path
    ) -> None:
        """Test error on invalid data."""
        with pytest.raises(ImportValidationError) as exc_info:
            await importer.parse_items(invalid_bad_data_csv, "test_user")

        error_msg = str(exc_info.value).lower()
        assert "count" in error_msg or "quantity" in error_msg

    @pytest.mark.asyncio
    async def test_parse_items_nonexistent_file(
        self, importer: MoxfieldCSVImporter
    ) -> None:
        """Test error on nonexistent file."""
        nonexistent = Path("nonexistent.csv")
        with pytest.raises(ImportFileError):
            await importer.parse_items(nonexistent, "test_user")

    @pytest.mark.asyncio
    async def test_validate_file_valid(
        self, importer: MoxfieldCSVImporter, valid_minimal_csv: Path
    ) -> None:
        """Test file validation for valid file."""
        response = await importer.validate_file(valid_minimal_csv)

        assert response.success
        assert not response.has_errors
        assert response.items_processed == 3
        assert response.validation_only

    @pytest.mark.asyncio
    async def test_validate_file_invalid(
        self, importer: MoxfieldCSVImporter, invalid_bad_data_csv: Path
    ) -> None:
        """Test file validation for invalid file."""
        response = await importer.validate_file(invalid_bad_data_csv)

        assert not response.success
        assert response.has_errors
        assert response.validation_only

    @pytest.mark.asyncio
    async def test_import_collection_success(
        self, importer: MoxfieldCSVImporter, valid_minimal_csv: Path
    ) -> None:
        """Test successful collection import."""
        request = ImportRequest(
            file_path=valid_minimal_csv, user_id="test_user", validate_only=False
        )

        response = await importer.import_collection(request)

        assert response.success
        assert not response.has_errors
        assert response.items_imported == 3
        assert response.items_processed == 3
        assert not response.validation_only
        assert response.processing_time_seconds is not None
        assert response.processing_time_seconds > 0

    @pytest.mark.asyncio
    async def test_import_collection_validation_only(
        self, importer: MoxfieldCSVImporter, valid_minimal_csv: Path
    ) -> None:
        """Test validation-only import."""
        request = ImportRequest(
            file_path=valid_minimal_csv, user_id="test_user", validate_only=True
        )

        response = await importer.import_collection(request)

        assert response.success
        assert response.validation_only
        assert response.items_imported == 0  # No actual import in validation mode
        assert response.items_processed == 3

    @pytest.mark.asyncio
    async def test_import_collection_transformation(
        self, importer: MoxfieldCSVImporter, valid_minimal_csv: Path
    ) -> None:
        """Test that raw data is automatically transformed to main collections table."""
        request = ImportRequest(
            file_path=valid_minimal_csv,
            user_id="transform_test_user",
            validate_only=False,
        )

        # Import the collection
        response = await importer.import_collection(request)

        assert response.success
        assert response.items_imported == 3

        # Verify data exists in both raw and main collections tables
        raw_count = importer.db_connection.fetch_one(
            "SELECT COUNT(*) FROM user_collections_raw WHERE user_id = ?",
            ("transform_test_user",),
        )
        main_count = importer.db_connection.fetch_one(
            "SELECT COUNT(*) FROM user_collections WHERE user_id = ?",
            ("transform_test_user",),
        )

        assert raw_count[0] == 3  # Raw data preserved
        assert main_count[0] == 3  # Data transformed to main table

        # Verify transformation quality - check a specific card
        card_data = importer.db_connection.fetch_one(
            "SELECT card_name, quantity, source_id FROM user_collections WHERE user_id = ? LIMIT 1",
            ("transform_test_user",),
        )

        assert card_data is not None
        assert card_data[1] > 0  # Has quantity
        assert card_data[2] == "moxfield"  # Source set correctly
