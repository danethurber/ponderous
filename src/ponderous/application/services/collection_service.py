"""Collection management application service."""

import logging
from pathlib import Path

from ponderous.infrastructure.importers import (
    CollectionImporter,
    ImportRequest,
    ImportResponse,
    MoxfieldCSVImporter,
)
from ponderous.shared.exceptions import PonderousError

logger = logging.getLogger(__name__)


class CollectionService:
    """Application service for collection management operations."""

    def __init__(self) -> None:
        """Initialize collection service."""
        logger.info("Initialized CollectionService")

    async def import_collection_from_file(
        self,
        file_path: Path,
        user_id: str,
        import_format: str = "moxfield_csv",
        validate_only: bool = False,
        skip_duplicates: bool = True,
    ) -> ImportResponse:
        """Import collection data from a file.

        Args:
            file_path: Path to collection file
            user_id: User identifier for collection
            import_format: File format (currently supports 'moxfield_csv')
            validate_only: Whether to only validate without importing
            skip_duplicates: Whether to skip duplicate entries

        Returns:
            Import operation result

        Raises:
            PonderousError: If import operation fails
        """
        if not file_path.exists():
            raise PonderousError(f"File not found: {file_path}")

        if not user_id or not user_id.strip():
            raise PonderousError("User ID cannot be empty")

        logger.info(f"Starting collection import from {file_path} for user {user_id}")

        try:
            # Create appropriate importer
            importer = self._get_importer(import_format)

            # Verify file format is supported
            if not importer.supports_format(file_path):
                raise PonderousError(
                    f"File format not supported by {import_format} importer: {file_path.suffix}"
                )

            # Create import request
            request = ImportRequest(
                file_path=file_path,
                user_id=user_id.strip(),
                source=f"{import_format}_import",
                validate_only=validate_only,
                skip_duplicates=skip_duplicates,
            )

            # Perform import
            response = await importer.import_collection(request)

            if response.success:
                if validate_only:
                    logger.info(
                        f"File validation successful: {response.items_processed} items validated"
                    )
                else:
                    logger.info(
                        f"Collection import successful: {response.items_imported} items imported"
                    )
            else:
                logger.error(f"Collection import failed: {response.errors}")

            return response

        except Exception as e:
            logger.error(f"Collection import failed for {file_path}: {e}")
            if not isinstance(e, PonderousError):
                raise PonderousError(f"Collection import failed: {e}") from e
            raise

    async def validate_collection_file(
        self,
        file_path: Path,
        import_format: str = "moxfield_csv",
    ) -> ImportResponse:
        """Validate collection file format without importing data.

        Args:
            file_path: Path to collection file
            import_format: File format to validate against

        Returns:
            Validation result

        Raises:
            PonderousError: If validation fails
        """
        logger.info(f"Validating collection file: {file_path}")

        try:
            importer = self._get_importer(import_format)
            return await importer.validate_file(file_path)

        except Exception as e:
            logger.error(f"File validation failed for {file_path}: {e}")
            if not isinstance(e, PonderousError):
                raise PonderousError(f"File validation failed: {e}") from e
            raise

    def get_supported_import_formats(self) -> list[str]:
        """Get list of supported import formats.

        Returns:
            List of supported format names
        """
        return ["moxfield_csv"]

    def _get_importer(self, import_format: str) -> CollectionImporter:
        """Get appropriate importer for format.

        Args:
            import_format: Format name

        Returns:
            Importer instance

        Raises:
            PonderousError: If format is not supported
        """
        if import_format.lower() == "moxfield_csv":
            return MoxfieldCSVImporter()
        else:
            raise PonderousError(f"Unsupported import format: {import_format}")
