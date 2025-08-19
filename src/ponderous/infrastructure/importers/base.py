"""Base classes and data models for collection imports."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel, Field

from ponderous.domain.models.collection import CollectionItem


@dataclass(frozen=True)
class ImportRequest:
    """Request for importing collection data from a file."""

    file_path: Path
    user_id: str
    source: str = "file_import"
    validate_only: bool = False
    skip_duplicates: bool = True

    def __post_init__(self) -> None:
        """Validate import request data."""
        if not self.file_path.exists():
            raise FileNotFoundError(f"Import file not found: {self.file_path}")
        if not self.user_id.strip():
            raise ValueError("User ID cannot be empty")


class ImportResponse(BaseModel):
    """Response from collection import operation."""

    success: bool = Field(..., description="Whether import operation succeeded")
    items_processed: int = Field(0, ge=0, description="Number of items processed")
    items_imported: int = Field(
        0, ge=0, description="Number of items successfully imported"
    )
    items_skipped: int = Field(0, ge=0, description="Number of items skipped")
    errors: list[str] = Field(
        default_factory=list, description="List of error messages"
    )
    warnings: list[str] = Field(
        default_factory=list, description="List of warning messages"
    )
    processing_time_seconds: float | None = Field(
        None, ge=0, description="Import processing time"
    )
    validation_only: bool = Field(
        False, description="Whether this was validation-only run"
    )

    @property
    def total_items(self) -> int:
        """Total number of items processed."""
        return self.items_imported + self.items_skipped

    @property
    def success_rate(self) -> float:
        """Success rate as percentage."""
        if self.items_processed == 0:
            return 0.0
        return (self.items_imported / self.items_processed) * 100.0

    @property
    def has_errors(self) -> bool:
        """Whether any errors occurred during import."""
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        """Whether any warnings occurred during import."""
        return len(self.warnings) > 0


class CollectionImporter(ABC):
    """Abstract base class for collection importers."""

    @property
    @abstractmethod
    def supported_formats(self) -> list[str]:
        """List of supported file formats (extensions)."""
        pass

    @property
    @abstractmethod
    def source_name(self) -> str:
        """Name of the import source."""
        pass

    @abstractmethod
    async def validate_file(self, file_path: Path) -> ImportResponse:
        """Validate import file without importing data.

        Args:
            file_path: Path to file to validate

        Returns:
            ImportResponse with validation results
        """
        pass

    @abstractmethod
    async def import_collection(self, request: ImportRequest) -> ImportResponse:
        """Import collection data from file.

        Args:
            request: Import request configuration

        Returns:
            ImportResponse with import results
        """
        pass

    @abstractmethod
    async def parse_items(self, file_path: Path, user_id: str) -> list[CollectionItem]:
        """Parse collection items from file.

        Args:
            file_path: Path to file to parse
            user_id: User ID for collection items

        Returns:
            List of parsed collection items

        Raises:
            ImportValidationError: When file format or data is invalid
            ImportFileError: When file operations fail
        """
        pass

    def supports_format(self, file_path: Path) -> bool:
        """Check if file format is supported.

        Args:
            file_path: Path to check

        Returns:
            True if format is supported
        """
        return file_path.suffix.lower() in self.supported_formats
