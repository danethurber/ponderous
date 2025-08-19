"""Moxfield CSV collection importer."""

import csv
import logging
from datetime import UTC, datetime
from pathlib import Path
from time import time

from ponderous.domain.models.collection import CollectionItem
from ponderous.infrastructure.database import (
    CollectionRepository,
    DatabaseConnection,
    DatabaseMigrator,
    get_database_connection,
)
from ponderous.infrastructure.database.repositories.collection_repository import (
    CollectionEntry,
    ImportSession,
)

from .base import CollectionImporter, ImportRequest, ImportResponse
from .exceptions import ImportFileError, ImportValidationError

logger = logging.getLogger(__name__)


class MoxfieldCSVImporter(CollectionImporter):
    """Importer for Moxfield CSV collection exports."""

    # Required columns for Moxfield CSV format
    REQUIRED_COLUMNS = {"Count", "Name", "Edition"}

    # Optional columns with default handling
    OPTIONAL_COLUMNS = {"Condition", "Language", "Foil", "Tag"}

    # All valid columns
    VALID_COLUMNS = REQUIRED_COLUMNS | OPTIONAL_COLUMNS

    # Valid foil values (case-insensitive)
    FOIL_VALUES = {"foil", "etched"}

    def __init__(self, db_connection: DatabaseConnection | None = None) -> None:
        """Initialize the importer with database connection.

        Args:
            db_connection: Optional database connection (for testing)
        """
        self.db_connection = db_connection or get_database_connection()
        self.repository = CollectionRepository(self.db_connection)

        # Ensure database is initialized
        migrator = DatabaseMigrator(self.db_connection)
        migrator.initialize_database()

    @property
    def supported_formats(self) -> list[str]:
        """List of supported file formats."""
        return [".csv"]

    @property
    def source_name(self) -> str:
        """Name of the import source."""
        return "moxfield_csv"

    async def validate_file(self, file_path: Path) -> ImportResponse:
        """Validate CSV file format and data."""
        start_time = time()

        try:
            # Parse items to validate structure and data
            items = await self.parse_items(file_path, "validation_user")

            return ImportResponse(
                success=True,
                items_processed=len(items),
                items_imported=0,
                items_skipped=0,
                validation_only=True,
                processing_time_seconds=time() - start_time,
            )

        except (ImportValidationError, ImportFileError) as e:
            return ImportResponse(
                success=False,
                items_processed=0,
                items_imported=0,
                items_skipped=0,
                errors=[str(e)],
                validation_only=True,
                processing_time_seconds=time() - start_time,
            )

    async def import_collection(self, request: ImportRequest) -> ImportResponse:
        """Import collection from CSV file."""
        start_time = time()

        try:
            # Parse collection entries directly (preserves all CSV data)
            collection_entries = await self.parse_collection_entries(
                request.file_path, request.user_id
            )

            items_imported = 0
            items_skipped = 0

            # If not validation-only, store to database
            if not request.validate_only:
                # Ensure user exists
                self.repository.create_user_if_not_exists(
                    request.user_id, request.user_id
                )

                # Store collection entries
                items_imported, items_skipped = (
                    self.repository.store_collection_entries(
                        collection_entries, skip_duplicates=request.skip_duplicates
                    )
                )

                # Store import session info
                import_session = ImportSession(
                    user_id=request.user_id,
                    file_path=str(request.file_path),
                    format="moxfield_csv",
                    items_processed=len(collection_entries),
                    items_imported=items_imported,
                    items_skipped=items_skipped,
                    success_rate=(
                        (items_imported / len(collection_entries)) * 100
                        if collection_entries
                        else 100
                    ),
                    processing_time_seconds=time() - start_time,
                )
                self.repository.store_import_session(import_session)

            logger.info(
                f"Successfully processed {len(collection_entries)} items from {request.file_path} "
                f"(imported: {items_imported}, skipped: {items_skipped})"
            )

            return ImportResponse(
                success=True,
                items_processed=len(collection_entries),
                items_imported=items_imported,
                items_skipped=items_skipped,
                validation_only=request.validate_only,
                processing_time_seconds=time() - start_time,
            )

        except (ImportValidationError, ImportFileError) as e:
            logger.error(f"Import failed for {request.file_path}: {e}")
            return ImportResponse(
                success=False,
                items_processed=0,
                items_imported=0,
                items_skipped=0,
                errors=[str(e)],
                validation_only=request.validate_only,
                processing_time_seconds=time() - start_time,
            )

    async def parse_items(self, file_path: Path, user_id: str) -> list[CollectionItem]:
        """Parse collection items from Moxfield CSV file."""
        if not file_path.exists():
            raise ImportFileError(f"File not found: {file_path}")

        if not file_path.suffix.lower() == ".csv":
            raise ImportValidationError(f"Unsupported file format: {file_path.suffix}")

        items = []

        try:
            with open(file_path, encoding="utf-8") as csvfile:
                # Detect delimiter and parse CSV
                sample = csvfile.read(1024)
                csvfile.seek(0)

                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter

                reader = csv.DictReader(csvfile, delimiter=delimiter)

                # Validate required columns
                if not reader.fieldnames:
                    raise ImportValidationError("CSV file has no headers")

                fieldnames = set(reader.fieldnames)
                missing_required = self.REQUIRED_COLUMNS - fieldnames
                if missing_required:
                    raise ImportValidationError(
                        f"Missing required columns: {', '.join(sorted(missing_required))}"
                    )

                # Parse each row
                for line_num, row in enumerate(
                    reader, start=2
                ):  # Start at 2 (header is line 1)
                    try:
                        item = self._parse_row(row, user_id, line_num)
                        items.append(item)
                    except ValueError as e:
                        raise ImportValidationError(str(e), line_number=line_num) from e

        except csv.Error as e:
            raise ImportValidationError(f"CSV parsing error: {e}") from e
        except OSError as e:
            raise ImportFileError(f"File reading error: {e}") from e

        if not items:
            raise ImportValidationError("No valid items found in CSV file")

        logger.info(f"Parsed {len(items)} items from {file_path}")
        return items

    def _parse_row(
        self, row: dict[str, str], user_id: str, line_num: int
    ) -> CollectionItem:
        """Parse a single CSV row into a CollectionItem."""
        try:
            # Parse count (required, must be positive integer)
            count_str = row.get("Count", "").strip()
            if not count_str:
                raise ValueError("Count field cannot be empty")

            try:
                count = int(count_str)
            except ValueError as e:
                raise ValueError(
                    f"Count must be a valid integer, got: '{count_str}'"
                ) from e

            if count <= 0:
                raise ValueError(f"Count must be positive, got: {count}")

            # Parse name (required, cannot be empty)
            name = row.get("Name", "").strip()
            if not name:
                raise ValueError("Name field cannot be empty")

            # Parse edition (required, cannot be empty)
            edition = row.get("Edition", "").strip()
            if not edition:
                raise ValueError("Edition field cannot be empty")

            # Parse foil status (optional)
            foil_str = row.get("Foil", "").strip().lower()
            is_foil = foil_str in self.FOIL_VALUES

            # Determine regular vs foil quantities
            if is_foil:
                quantity = 0
                foil_quantity = count
            else:
                quantity = count
                foil_quantity = 0

            # Generate source_id and card_id (using name + edition for uniqueness)
            source_id = f"moxfield_csv_{line_num}"
            card_id = f"{name}_{edition}".replace(" ", "_").lower()

            return CollectionItem(
                user_id=user_id,
                source_id=source_id,
                card_id=card_id,
                card_name=name,
                quantity=quantity,
                foil_quantity=foil_quantity,
                last_updated=datetime.now(UTC),
            )

        except ValueError:
            # Re-raise ValueError with line context
            raise
        except Exception as e:
            raise ValueError(f"Error parsing row: {e}") from e

    async def parse_collection_entries(
        self, file_path: Path, user_id: str
    ) -> list[CollectionEntry]:
        """Parse collection entries directly from CSV for database storage.

        Args:
            file_path: Path to CSV file
            user_id: User identifier

        Returns:
            List of collection entries for database storage
        """
        if not file_path.exists():
            raise ImportFileError(f"File not found: {file_path}")

        if not file_path.suffix.lower() == ".csv":
            raise ImportValidationError(f"Unsupported file format: {file_path.suffix}")

        entries = []

        try:
            with open(file_path, encoding="utf-8") as csvfile:
                # Detect delimiter and parse CSV
                sample = csvfile.read(1024)
                csvfile.seek(0)

                sniffer = csv.Sniffer()
                delimiter = sniffer.sniff(sample).delimiter

                reader = csv.DictReader(csvfile, delimiter=delimiter)

                # Validate required columns
                if not reader.fieldnames:
                    raise ImportValidationError("CSV file has no headers")

                fieldnames = set(reader.fieldnames)
                missing_required = self.REQUIRED_COLUMNS - fieldnames
                if missing_required:
                    raise ImportValidationError(
                        f"Missing required columns: {', '.join(sorted(missing_required))}"
                    )

                # Parse each row directly to collection entries
                for line_num, row in enumerate(reader, start=2):
                    try:
                        entry = self._parse_row_to_entry(row, user_id, line_num)
                        entries.append(entry)
                    except ValueError as e:
                        raise ImportValidationError(str(e), line_number=line_num) from e

        except csv.Error as e:
            raise ImportValidationError(f"CSV parsing error: {e}") from e
        except OSError as e:
            raise ImportFileError(f"File reading error: {e}") from e

        if not entries:
            raise ImportValidationError("No valid items found in CSV file")

        logger.info(f"Parsed {len(entries)} collection entries from {file_path}")
        return entries

    def _parse_row_to_entry(
        self,
        row: dict[str, str],
        user_id: str,
        line_num: int,  # noqa: ARG002
    ) -> CollectionEntry:
        """Parse a single CSV row into a CollectionEntry for database storage.

        Args:
            row: CSV row data
            user_id: User identifier
            line_num: Line number for error reporting

        Returns:
            CollectionEntry for database storage
        """
        try:
            # Parse count (required, must be positive integer)
            count_str = row.get("Count", "").strip()
            if not count_str:
                raise ValueError("Count field cannot be empty")

            try:
                count = int(count_str)
            except ValueError as e:
                raise ValueError(
                    f"Count must be a valid integer, got: '{count_str}'"
                ) from e

            if count <= 0:
                raise ValueError(f"Count must be positive, got: {count}")

            # Parse name (required, cannot be empty)
            name = row.get("Name", "").strip()
            if not name:
                raise ValueError("Name field cannot be empty")

            # Parse edition (required, cannot be empty)
            edition = row.get("Edition", "").strip()
            if not edition:
                raise ValueError("Edition field cannot be empty")

            # Parse optional fields with proper defaults
            condition = row.get("Condition", "").strip() or None
            language = row.get("Language", "").strip() or "English"
            tags = row.get("Tag", "").strip() or None

            # Parse foil status (optional)
            foil_str = row.get("Foil", "").strip().lower()
            is_foil = foil_str in self.FOIL_VALUES

            return CollectionEntry(
                user_id=user_id,
                card_name=name,
                set_name=edition,
                quantity=count,
                condition=condition,
                language=language,
                foil=is_foil,
                tags=tags,
                import_source="moxfield_csv",
            )

        except ValueError:
            # Re-raise ValueError with line context
            raise
        except Exception as e:
            raise ValueError(f"Error parsing row: {e}") from e
