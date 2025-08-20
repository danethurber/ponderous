"""
Progress indicator formatters for CLI operations.

Provides consistent progress indicators for long-running operations.
"""

from typing import Any

from .base import BaseFormatter


class ProgressFormatter(BaseFormatter):
    """Formatter for progress indicators during operations."""

    def format(self, data: Any) -> None:
        """Format and display basic progress data."""
        self.console.print(f"Progress: {data}")

    def format_import_progress(self, response: Any) -> None:
        """Format import progress messages."""
        if response.success:
            if hasattr(response, "validation_only") and response.validation_only:
                self.console.print(
                    "🎉 [bold green]File validation completed![/bold green]"
                )
            else:
                self.console.print(
                    "🎉 [bold green]Collection import completed![/bold green]"
                )

            self.console.print(f"📊 {response.items_processed} items processed")

            if not (hasattr(response, "validation_only") and response.validation_only):
                self.console.print(f"📥 {response.items_imported} items imported")

            if response.processing_time_seconds:
                self.console.print(
                    f"⏱️  Completed in {response.processing_time_seconds:.2f} seconds"
                )
        else:
            self.console.print("[bold red]❌ Collection import failed![/bold red]")

    def format_warnings(self, response: Any) -> None:
        """Format warning messages."""
        if response.has_warnings:
            self.console.print("\n⚠️  [bold yellow]Warnings:[/bold yellow]")
            for warning in response.warnings:
                self.console.print(f"   • {warning}")

    def format_errors(self, response: Any) -> None:
        """Format error messages."""
        if response.has_errors:
            self.console.print("\n💥 [bold red]Errors:[/bold red]")
            for error in response.errors:
                self.console.print(f"   • {error}")
