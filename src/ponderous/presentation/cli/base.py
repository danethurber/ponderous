"""
Base CLI functionality and shared utilities.

Contains common patterns used across CLI commands including error handling,
database connections, and progress indicators.
"""

import sys
from collections.abc import Callable
from functools import wraps
from typing import TYPE_CHECKING, Any, TypeVar

if TYPE_CHECKING:
    from ponderous.infrastructure.database import DatabaseConnection

import click
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)

from ponderous.infrastructure.database import get_database_connection
from ponderous.shared.config import get_config
from ponderous.shared.exceptions import PonderousError

# Use unlimited width to prevent path truncation in tests
console = Console(width=None)

F = TypeVar("F", bound=Callable[..., Any])

CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "max_content_width": 120,
}


class PonderousContext:
    """CLI context object to pass data between commands."""

    def __init__(self) -> None:
        self.config = get_config()
        self.debug = self.config.debug
        self.verbose = False


def handle_exception(func: F) -> F:
    """Decorator to handle exceptions gracefully in CLI commands."""

    @wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        try:
            return func(*args, **kwargs)
        except PonderousError as e:
            console.print(f"[red]Error:[/red] {e}", style="bold red")
            if click.get_current_context().obj.debug:
                console.print_exception(show_locals=True)
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]Unexpected error:[/red] {e}", style="bold red")
            if click.get_current_context().obj.debug:
                console.print_exception(show_locals=True)
            sys.exit(1)

    return wrapper  # type: ignore[return-value]


def create_progress() -> Progress:
    """Create a standard progress indicator."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console,
    )


def create_simple_progress() -> Progress:
    """Create a simple progress indicator without progress bar."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    )


class DatabaseMixin:
    """Mixin for commands that need database connections."""

    def __init__(self) -> None:
        self._db_connection: DatabaseConnection | None = None

    def get_db_connection(self) -> "DatabaseConnection":
        """Get database connection, creating if needed."""
        if self._db_connection is None:
            self._db_connection = get_database_connection()
        return self._db_connection

    def close_db_connection(self) -> None:
        """Close database connection if open."""
        if self._db_connection:
            self._db_connection.close()
            self._db_connection = None


# Common CLI options that can be reused
common_user_id_option = click.option("--user-id", required=True, help="User identifier")

common_limit_option = click.option(
    "--limit", default=10, type=int, help="Maximum number of results"
)

common_verbose_option = click.option(
    "--verbose", "-v", is_flag=True, help="Enable verbose output"
)

# Common argument types
BudgetChoice = click.Choice(["budget", "mid", "high", "cedh"], case_sensitive=False)
OutputFormatChoice = click.Choice(["table", "json", "csv"], case_sensitive=False)
SortChoice = click.Choice(
    ["completion", "buildability", "popularity", "power-level", "budget"],
    case_sensitive=False,
)


def success_message(message: str) -> None:
    """Display a success message."""
    console.print(f"🎉 [bold green]{message}[/bold green]")


def warning_message(message: str) -> None:
    """Display a warning message."""
    console.print(f"⚠️  [bold yellow]{message}[/bold yellow]")


def error_message(message: str) -> None:
    """Display an error message."""
    console.print(f"❌ [bold red]{message}[/bold red]")


def info_message(message: str) -> None:
    """Display an info message."""
    console.print(f"ℹ️  [cyan]{message}[/cyan]")
