"""
Base validator classes for CLI input validation.

Provides foundation classes for validating user input across commands.
"""

from abc import ABC, abstractmethod
from typing import Any

from ponderous.shared.exceptions import PonderousError


class ValidationError(PonderousError):
    """Raised when validation fails."""

    pass


class BaseValidator(ABC):
    """Base class for all validators."""

    @abstractmethod
    def validate(self, value: Any) -> bool:
        """Validate a value and return True if valid."""
        pass

    def validate_or_raise(self, value: Any) -> None:
        """Validate a value and raise ValidationError if invalid."""
        if not self.validate(value):
            raise ValidationError(f"Invalid value: {value}")
