"""Moxfield API specific exceptions."""

from ponderous.shared.exceptions import PonderousError


class MoxfieldAPIError(PonderousError):
    """Base exception for Moxfield API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        self.status_code = status_code
        super().__init__(message)

    def __str__(self) -> str:
        if self.status_code:
            return f"Moxfield API error {self.status_code}: {super().__str__()}"
        return f"Moxfield API error: {super().__str__()}"


class MoxfieldAuthError(MoxfieldAPIError):
    """Raised when authentication fails."""

    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, status_code=401)


class MoxfieldRateLimitError(MoxfieldAPIError):
    """Raised when rate limit is exceeded."""

    def __init__(
        self, message: str = "Rate limit exceeded", retry_after: int | None = None
    ) -> None:
        super().__init__(message, status_code=429)
        self.retry_after = retry_after

    def __str__(self) -> str:
        base_message = super().__str__()
        if self.retry_after:
            return f"{base_message}. Retry after {self.retry_after} seconds."
        return base_message


class MoxfieldNotFoundError(MoxfieldAPIError):
    """Raised when a resource is not found."""

    def __init__(self, message: str = "Resource not found") -> None:
        super().__init__(message, status_code=404)


class MoxfieldValidationError(MoxfieldAPIError):
    """Raised when data validation fails."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)
