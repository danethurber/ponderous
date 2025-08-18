"""Custom exceptions for Ponderous application."""

from typing import Any


class PonderousError(Exception):
    """Base exception for all Ponderous errors."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        """Initialize PonderousError with message and optional details context."""
        super().__init__(message)
        self.message = message
        self.details = details or {}


class ValidationError(PonderousError):
    """Raised when data validation fails."""

    pass


class ConfigurationError(PonderousError):
    """Raised when configuration is invalid or missing."""

    pass


class DataSourceError(PonderousError):
    """Base exception for data source related errors."""

    pass


class MoxfieldAPIError(DataSourceError):
    """Raised when Moxfield API request fails."""

    def __init__(
        self, status_code: int, message: str, username: str | None = None
    ) -> None:
        """Initialize MoxfieldAPIError with status code and optional username context."""
        self.status_code = status_code
        self.username = username
        details: dict[str, Any] = {"status_code": status_code}
        if username:
            details["username"] = username
        super().__init__(f"Moxfield API error {status_code}: {message}", details)


class EDHRECError(DataSourceError):
    """Raised when EDHREC scraping fails."""

    def __init__(
        self, message: str, commander: str | None = None, url: str | None = None
    ) -> None:
        """Initialize EDHRECError with optional commander and URL context."""
        self.commander = commander
        self.url = url
        details = {}
        if commander:
            details["commander"] = commander
        if url:
            details["url"] = url
        super().__init__(f"EDHREC error: {message}", details)


class DatabaseError(PonderousError):
    """Raised when database operations fail."""

    def __init__(self, message: str, query: str | None = None) -> None:
        """Initialize DatabaseError with optional failing SQL query context."""
        self.query = query
        details = {}
        if query:
            details["query"] = query
        super().__init__(f"Database error: {message}", details)


class AnalysisError(PonderousError):
    """Raised when deck analysis operations fail."""

    def __init__(
        self, message: str, commander: str | None = None, user_id: str | None = None
    ) -> None:
        """Initialize AnalysisError with optional commander and user context."""
        self.commander = commander
        self.user_id = user_id
        details = {}
        if commander:
            details["commander"] = commander
        if user_id:
            details["user_id"] = user_id
        super().__init__(f"Analysis error: {message}", details)


class CollectionError(PonderousError):
    """Raised when collection operations fail."""

    def __init__(
        self, message: str, user_id: str | None = None, source: str | None = None
    ) -> None:
        """Initialize CollectionError with optional user and source context."""
        self.user_id = user_id
        self.source = source
        details = {}
        if user_id:
            details["user_id"] = user_id
        if source:
            details["source"] = source
        super().__init__(f"Collection error: {message}", details)


class RateLimitError(DataSourceError):
    """Raised when rate limits are exceeded."""

    def __init__(self, message: str, retry_after: float | None = None) -> None:
        """Initialize RateLimitError with optional retry delay information."""
        self.retry_after = retry_after
        details = {}
        if retry_after:
            details["retry_after"] = retry_after
        super().__init__(f"Rate limit exceeded: {message}", details)


class NotFoundError(PonderousError):
    """Raised when requested resource is not found."""

    def __init__(self, resource_type: str, identifier: str) -> None:
        """Initialize NotFoundError with resource type and identifier for context."""
        self.resource_type = resource_type
        self.identifier = identifier
        details = {"resource_type": resource_type, "identifier": identifier}
        super().__init__(f"{resource_type} not found: {identifier}", details)
