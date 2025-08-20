"""
Collection-specific validators for CLI input.

Validates collection-related inputs like file formats and user IDs.
"""

from pathlib import Path

from .base import BaseValidator, ValidationError


class CollectionFileValidator(BaseValidator):
    """Validator for collection file formats."""

    SUPPORTED_EXTENSIONS = {".csv"}

    def validate(self, file_path: Path) -> bool:
        """Validate that the file has a supported extension."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS

    def validate_or_raise(self, file_path: Path) -> None:
        """Validate file path and raise ValidationError if invalid."""
        if not self.validate(file_path):
            raise ValidationError(
                f"Unsupported file format: {file_path.suffix}. "
                f"Supported formats: {', '.join(self.SUPPORTED_EXTENSIONS)}"
            )


class ColorIdentityValidator(BaseValidator):
    """Validator for MTG color identity strings."""

    VALID_COLORS = {"W", "U", "B", "R", "G"}

    def validate(self, colors: str) -> bool:
        """Validate that color string contains only valid MTG colors."""
        if not colors:
            return True

        color_set = set(colors.upper())
        return color_set.issubset(self.VALID_COLORS)

    def validate_or_raise(self, colors: str) -> None:
        """Validate colors and raise ValidationError if invalid."""
        if not self.validate(colors):
            invalid_colors = set(colors.upper()) - self.VALID_COLORS
            raise ValidationError(
                f"Invalid colors: {', '.join(invalid_colors)}. "
                f"Valid colors: {', '.join(sorted(self.VALID_COLORS))}"
            )

    def parse_colors(self, colors: str) -> list[str]:
        """Parse color string into list, validating first."""
        if not colors:
            return []

        self.validate_or_raise(colors)
        return list(colors.replace(",", "").upper())


class UserIdValidator(BaseValidator):
    """Validator for user IDs."""

    MIN_LENGTH = 1
    MAX_LENGTH = 100

    def validate(self, user_id: str) -> bool:
        """Validate user ID length and format."""
        if not user_id or not isinstance(user_id, str):
            return False

        user_id = user_id.strip()
        return self.MIN_LENGTH <= len(user_id) <= self.MAX_LENGTH

    def validate_or_raise(self, user_id: str) -> None:
        """Validate user ID and raise ValidationError if invalid."""
        if not self.validate(user_id):
            raise ValidationError(
                f"Invalid user ID. Must be between {self.MIN_LENGTH} "
                f"and {self.MAX_LENGTH} characters."
            )
