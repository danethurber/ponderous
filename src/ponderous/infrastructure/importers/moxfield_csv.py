"""Moxfield CSV collection importer."""

import csv
import logging
from datetime import UTC, datetime
from pathlib import Path
from time import time

from ponderous.domain.models.collection import CollectionItem

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
            # Parse and validate items
            items = await self.parse_items(request.file_path, request.user_id)

            # If validation-only, don't actually import
            items_imported = 0 if request.validate_only else len(items)

            logger.info(
                f"Successfully imported {len(items)} items from {request.file_path}"
            )

            return ImportResponse(
                success=True,
                items_processed=len(items),
                items_imported=items_imported,
                items_skipped=0,
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
