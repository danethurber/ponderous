"""Unit tests for CollectionService."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from ponderous.application.services.collection_service import CollectionService
from ponderous.infrastructure.importers import ImportRequest, ImportResponse
from ponderous.shared.exceptions import PonderousError


class TestCollectionService:
    """Test suite for CollectionService."""

    def setup_method(self) -> None:
        """Set up test fixtures."""
        self.service = CollectionService()

        # Mock file path that exists
        self.mock_file_path = Mock()
        self.mock_file_path.exists.return_value = True
        self.mock_file_path.suffix = ".csv"
        self.mock_file_path.__str__ = Mock(return_value="/test/collection.csv")

        # Mock file path that doesn't exist
        self.mock_nonexistent_file = Mock()
        self.mock_nonexistent_file.exists.return_value = False
        self.mock_nonexistent_file.__str__ = Mock(return_value="/test/nonexistent.csv")

    @pytest.mark.asyncio
    async def test_import_collection_from_file_success(self) -> None:
        """Should successfully import collection from file."""
        # Arrange
        mock_response = ImportResponse(
            success=True,
            items_processed=100,
            items_imported=95,
            items_skipped=5,
            errors=[],
            warnings=["5 duplicate cards skipped"],
        )

        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.supports_format.return_value = True
            mock_importer.import_collection.return_value = mock_response
            mock_get_importer.return_value = mock_importer

            # Act
            result = await self.service.import_collection_from_file(
                file_path=self.mock_file_path,
                user_id="test_user",
                import_format="moxfield_csv",
            )

            # Assert
            assert result.success is True
            assert result.items_imported == 95
            assert result.items_processed == 100
            assert result.items_skipped == 5

            # Verify importer was called correctly
            mock_importer.import_collection.assert_called_once()
            call_args = mock_importer.import_collection.call_args[0][0]
            assert isinstance(call_args, ImportRequest)
            assert call_args.user_id == "test_user"
            assert call_args.file_path == self.mock_file_path
            assert call_args.validate_only is False
            assert call_args.skip_duplicates is True

    @pytest.mark.asyncio
    async def test_import_collection_from_file_validation_only(self) -> None:
        """Should validate file without importing when validate_only=True."""
        # Arrange
        mock_response = ImportResponse(
            success=True,
            items_processed=100,
            items_imported=0,  # No import in validation mode
            items_skipped=0,
            errors=[],
            warnings=[],
            validation_only=True,
        )

        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.supports_format.return_value = True
            mock_importer.import_collection.return_value = mock_response
            mock_get_importer.return_value = mock_importer

            # Act
            result = await self.service.import_collection_from_file(
                file_path=self.mock_file_path, user_id="test_user", validate_only=True
            )

            # Assert
            assert result.success is True
            assert result.items_imported == 0  # No actual import
            assert result.items_processed == 100

            # Verify validation mode was set
            call_args = mock_importer.import_collection.call_args[0][0]
            assert call_args.validate_only is True

    @pytest.mark.asyncio
    async def test_import_collection_file_not_found(self) -> None:
        """Should raise PonderousError when file doesn't exist."""
        # Act & Assert
        with pytest.raises(PonderousError, match="File not found"):
            await self.service.import_collection_from_file(
                file_path=self.mock_nonexistent_file, user_id="test_user"
            )

    @pytest.mark.asyncio
    async def test_import_collection_empty_user_id(self) -> None:
        """Should raise PonderousError when user_id is empty."""
        test_cases = ["", "   ", None]

        for user_id in test_cases:
            with pytest.raises(PonderousError, match="User ID cannot be empty"):
                await self.service.import_collection_from_file(
                    file_path=self.mock_file_path, user_id=user_id
                )

    @pytest.mark.asyncio
    async def test_import_collection_unsupported_format(self) -> None:
        """Should raise PonderousError for unsupported file formats."""
        # Act & Assert
        with pytest.raises(PonderousError, match="Unsupported import format"):
            await self.service.import_collection_from_file(
                file_path=self.mock_file_path,
                user_id="test_user",
                import_format="unsupported_format",
            )

    @pytest.mark.asyncio
    async def test_import_collection_file_format_not_supported_by_importer(
        self,
    ) -> None:
        """Should raise PonderousError when importer doesn't support file format."""
        # Arrange
        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = Mock()  # Use regular Mock
            mock_importer.supports_format.return_value = (
                False  # Importer rejects format
            )
            mock_get_importer.return_value = mock_importer

            # Act & Assert
            with pytest.raises(PonderousError, match="File format not supported"):
                await self.service.import_collection_from_file(
                    file_path=self.mock_file_path, user_id="test_user"
                )

    @pytest.mark.asyncio
    async def test_import_collection_importer_failure(self) -> None:
        """Should handle importer failures gracefully."""
        # Arrange
        mock_response = ImportResponse(
            success=False,
            items_processed=50,
            items_imported=0,
            items_skipped=0,
            errors=["Invalid CSV format on row 25", "Missing required column: Name"],
            warnings=[],
        )

        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.supports_format.return_value = True
            mock_importer.import_collection.return_value = mock_response
            mock_get_importer.return_value = mock_importer

            # Act
            result = await self.service.import_collection_from_file(
                file_path=self.mock_file_path, user_id="test_user"
            )

            # Assert
            assert result.success is False
            assert len(result.errors) == 2
            assert "Invalid CSV format on row 25" in result.errors

    @pytest.mark.asyncio
    async def test_import_collection_exception_handling(self) -> None:
        """Should wrap unexpected exceptions in PonderousError."""
        # Arrange
        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.supports_format.return_value = True
            mock_importer.import_collection.side_effect = ValueError("Unexpected error")
            mock_get_importer.return_value = mock_importer

            # Act & Assert
            with pytest.raises(PonderousError, match="Collection import failed"):
                await self.service.import_collection_from_file(
                    file_path=self.mock_file_path, user_id="test_user"
                )

    @pytest.mark.asyncio
    async def test_validate_collection_file_success(self) -> None:
        """Should successfully validate collection file."""
        # Arrange
        mock_response = ImportResponse(
            success=True,
            items_processed=150,  # Estimated records
            items_imported=0,
            items_skipped=0,
            errors=[],
            warnings=[],
            validation_only=True,
        )

        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.validate_file.return_value = mock_response
            mock_get_importer.return_value = mock_importer

            # Act
            result = await self.service.validate_collection_file(self.mock_file_path)

            # Assert
            assert result.success is True
            assert result.validation_only is True
            assert result.items_processed == 150
            mock_importer.validate_file.assert_called_once_with(self.mock_file_path)

    @pytest.mark.asyncio
    async def test_validate_collection_file_validation_errors(self) -> None:
        """Should return validation errors when file format is invalid."""
        # Arrange
        mock_response = ImportResponse(
            success=False,
            items_processed=0,
            items_imported=0,
            items_skipped=0,
            errors=[
                "Missing required column: Name",
                "Invalid CSV format: row 5 has wrong number of columns",
            ],
            warnings=["File contains special characters"],
            validation_only=True,
        )

        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.validate_file.return_value = mock_response
            mock_get_importer.return_value = mock_importer

            # Act
            result = await self.service.validate_collection_file(self.mock_file_path)

            # Assert
            assert result.success is False
            assert len(result.errors) == 2
            assert "Missing required column: Name" in result.errors

    @pytest.mark.asyncio
    async def test_validate_collection_file_exception_handling(self) -> None:
        """Should wrap validation exceptions in PonderousError."""
        # Arrange
        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.validate_file.side_effect = OSError("File read error")
            mock_get_importer.return_value = mock_importer

            # Act & Assert
            with pytest.raises(PonderousError, match="File validation failed"):
                await self.service.validate_collection_file(self.mock_file_path)

    def test_get_supported_import_formats(self) -> None:
        """Should return list of supported import formats."""
        # Act
        formats = self.service.get_supported_import_formats()

        # Assert
        assert isinstance(formats, list)
        assert "moxfield_csv" in formats
        assert len(formats) >= 1  # Should support at least Moxfield CSV

    def test_get_importer_moxfield_csv(self) -> None:
        """Should return MoxfieldCSVImporter for moxfield_csv format."""
        # Act
        importer = self.service._get_importer("moxfield_csv")

        # Assert
        assert importer is not None
        from ponderous.infrastructure.importers import MoxfieldCSVImporter

        assert isinstance(importer, MoxfieldCSVImporter)

    def test_get_importer_case_insensitive(self) -> None:
        """Should handle case-insensitive format names."""
        # Act
        importer1 = self.service._get_importer("MOXFIELD_CSV")
        importer2 = self.service._get_importer("Moxfield_Csv")

        # Assert
        from ponderous.infrastructure.importers import MoxfieldCSVImporter

        assert isinstance(importer1, MoxfieldCSVImporter)
        assert isinstance(importer2, MoxfieldCSVImporter)

    def test_get_importer_unsupported_format(self) -> None:
        """Should raise PonderousError for unsupported formats."""
        # Act & Assert
        with pytest.raises(PonderousError, match="Unsupported import format"):
            self.service._get_importer("unknown_format")

    @pytest.mark.asyncio
    async def test_import_collection_with_skip_duplicates_false(self) -> None:
        """Should include duplicate cards when skip_duplicates=False."""
        # Arrange
        mock_response = ImportResponse(
            success=True,
            items_processed=100,
            items_imported=100,  # All items imported including duplicates
            items_skipped=0,
            errors=[],
            warnings=["5 duplicates imported"],
        )

        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.supports_format.return_value = True
            mock_importer.import_collection.return_value = mock_response
            mock_get_importer.return_value = mock_importer

            # Act
            result = await self.service.import_collection_from_file(
                file_path=self.mock_file_path,
                user_id="test_user",
                skip_duplicates=False,
            )

            # Assert
            assert result.success is True
            assert result.items_skipped == 0  # No duplicates skipped

            # Verify skip_duplicates setting
            call_args = mock_importer.import_collection.call_args[0][0]
            assert call_args.skip_duplicates is False

    @pytest.mark.asyncio
    async def test_import_collection_user_id_whitespace_trimmed(self) -> None:
        """Should trim whitespace from user_id."""
        # Arrange
        mock_response = ImportResponse(
            success=True, items_processed=1, items_imported=1
        )

        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.supports_format.return_value = True
            mock_importer.import_collection.return_value = mock_response
            mock_get_importer.return_value = mock_importer

            # Act
            await self.service.import_collection_from_file(
                file_path=self.mock_file_path,
                user_id="  test_user  ",  # Whitespace around user ID
            )

            # Assert
            call_args = mock_importer.import_collection.call_args[0][0]
            assert call_args.user_id == "test_user"  # Trimmed

    @pytest.mark.asyncio
    async def test_import_collection_large_file_handling(self) -> None:
        """Should handle large collection files efficiently."""
        # Arrange - simulate large collection
        mock_response = ImportResponse(
            success=True,
            items_processed=5000,
            items_imported=4950,
            items_skipped=50,
            errors=[],
            warnings=["Large collection processed in batches"],
            processing_time_seconds=45.2,
        )

        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.supports_format.return_value = True
            mock_importer.import_collection.return_value = mock_response
            mock_get_importer.return_value = mock_importer

            # Act
            result = await self.service.import_collection_from_file(
                file_path=self.mock_file_path, user_id="test_user"
            )

            # Assert
            assert result.success is True
            assert result.items_processed == 5000
            assert result.items_imported == 4950
            assert result.processing_time_seconds == 45.2

    @pytest.mark.asyncio
    async def test_import_collection_concurrent_imports(self) -> None:
        """Should handle multiple concurrent import operations safely."""
        # This test would be more meaningful with actual database operations
        # For now, we test that the service doesn't block on multiple calls

        # Arrange
        mock_response = ImportResponse(
            success=True, items_processed=10, items_imported=10
        )

        with patch.object(self.service, "_get_importer") as mock_get_importer:
            mock_importer = AsyncMock()
            mock_importer.supports_format.return_value = True
            mock_importer.import_collection.return_value = mock_response
            mock_get_importer.return_value = mock_importer

            # Act - concurrent imports for different users
            import asyncio

            results = await asyncio.gather(
                self.service.import_collection_from_file(self.mock_file_path, "user1"),
                self.service.import_collection_from_file(self.mock_file_path, "user2"),
                self.service.import_collection_from_file(self.mock_file_path, "user3"),
            )

            # Assert
            assert len(results) == 3
            assert all(result.success for result in results)


# Additional test helpers
def create_mock_import_response(**kwargs) -> ImportResponse:
    """Create mock ImportResponse with defaults."""
    defaults = {
        "success": True,
        "items_processed": 100,
        "items_imported": 95,
        "items_skipped": 5,
        "errors": [],
        "warnings": [],
    }
    defaults.update(kwargs)
    return ImportResponse(**defaults)


def create_mock_file_path(exists: bool = True, suffix: str = ".csv") -> Mock:
    """Create mock file path for testing."""
    mock_path = Mock()
    mock_path.exists.return_value = exists
    mock_path.suffix = suffix
    mock_path.__str__ = Mock(return_value=f"/test/collection{suffix}")
    return mock_path
