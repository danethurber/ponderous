"""
Base formatter classes for CLI output.

Provides foundation classes for consistent formatting across commands.
"""

from abc import ABC, abstractmethod
from typing import Any

from rich.console import Console
from rich.table import Table


class BaseFormatter(ABC):
    """Base class for all formatters."""

    def __init__(self, console: Console | None = None) -> None:
        """Initialize formatter with optional console."""
        self.console = console or Console(width=None)

    @abstractmethod
    def format(self, data: Any) -> None:
        """Format and display data."""
        pass


class TableFormatter(BaseFormatter):
    """Base class for table-based formatters."""

    def create_table(
        self,
        title: str | None = None,
        show_header: bool = True,
        header_style: str = "bold magenta",
    ) -> Table:
        """Create a Rich table with standard styling."""
        return Table(
            title=title,
            show_header=show_header,
            header_style=header_style,
        )
