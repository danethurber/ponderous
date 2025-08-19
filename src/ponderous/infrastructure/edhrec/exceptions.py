"""EDHREC-specific exceptions."""


class EDHRECError(Exception):
    """Base exception for EDHREC operations."""

    def __init__(self, message: str, url: str | None = None) -> None:
        super().__init__(message)
        self.url = url


class EDHRECScrapingError(EDHRECError):
    """Exception raised when scraping fails."""

    pass


class EDHRECParsingError(EDHRECError):
    """Exception raised when parsing EDHREC data fails."""

    pass


class EDHRECRateLimitError(EDHRECError):
    """Exception raised when rate limit is exceeded."""

    pass


class EDHRECConnectionError(EDHRECError):
    """Exception raised when connection to EDHREC fails."""

    pass
