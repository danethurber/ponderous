"""Import-specific exceptions."""

from ponderous.shared.exceptions import PonderousError


class ImportError(PonderousError):
    """Base exception for import operations."""


class ImportValidationError(ImportError):
    """Exception raised when import data validation fails."""

    def __init__(
        self, message: str, line_number: int | None = None, field: str | None = None
    ) -> None:
        self.line_number = line_number
        self.field = field
        super().__init__(message)

    def __str__(self) -> str:
        if self.line_number is not None:
            if self.field:
                return f"Line {self.line_number}, field '{self.field}': {super().__str__()}"
            return f"Line {self.line_number}: {super().__str__()}"
        return super().__str__()


class ImportFileError(ImportError):
    """Exception raised when file operations fail."""


class ImportFormatError(ImportError):
    """Exception raised when file format is unsupported or malformed."""
