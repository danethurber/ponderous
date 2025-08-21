"""
Table formatting utilities for CLI output.

Provides specialized table formatters for different types of data.
"""

from typing import Any

from .base import TableFormatter


class CollectionSummaryFormatter(TableFormatter):
    """Formatter for collection summary data."""

    def format(self, summary: dict[str, Any]) -> None:
        """Format and display collection summary."""
        table = self.create_table()
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="cyan")

        table.add_row("Total Cards", str(summary["total_cards"]))
        table.add_row("Unique Cards", str(summary["unique_cards"]))
        table.add_row("Sets Represented", str(summary["sets_represented"]))
        table.add_row("Foil Cards", str(summary["foil_cards"]))

        if summary.get("last_import"):
            table.add_row("Last Import", str(summary["last_import"])[:19])

        self.console.print(table)


class CommanderRecommendationFormatter(TableFormatter):
    """Formatter for commander recommendation data."""

    def format(self, recommendations: list[Any]) -> None:
        """Format and display commander recommendations."""
        table = self.create_table()
        table.add_column("Rank", style="dim", width=4)
        table.add_column("Commander", style="cyan", min_width=20)
        table.add_column("Colors", style="bright_blue", width=6)
        table.add_column("Buildability", style="green", width=12)
        table.add_column("Cards Owned", style="yellow", width=11)
        table.add_column("Missing $", style="red", width=10)
        table.add_column("Power", style="magenta", width=6)

        for i, rec in enumerate(recommendations, 1):
            # Handle both dict and object formats
            def get_field(obj: Any, field: str) -> Any:
                return (
                    getattr(obj, field, None) if hasattr(obj, field) else obj.get(field)
                )

            color_identity = get_field(rec, "color_identity")
            colors = "".join(color_identity) if color_identity else "C"

            completion_percentage = get_field(rec, "completion_percentage")
            buildability = (
                f"{completion_percentage:.1%}" if completion_percentage else "N/A"
            )

            owned_cards = get_field(rec, "owned_cards")
            total_cards = get_field(rec, "total_cards")
            cards_owned = (
                f"{owned_cards}/{total_cards}" if owned_cards and total_cards else "N/A"
            )

            missing_cards_value = get_field(rec, "missing_cards_value")
            missing_value = (
                f"${missing_cards_value:.0f}" if missing_cards_value else "N/A"
            )

            power_level = get_field(rec, "power_level")
            power = f"{power_level:.1f}" if power_level else "N/A"

            commander_name = get_field(rec, "commander_name") or "Unknown"

            table.add_row(
                str(i),
                commander_name,
                colors,
                buildability,
                cards_owned,
                missing_value,
                power,
            )

        self.console.print(table)


class ImportSummaryFormatter(TableFormatter):
    """Formatter for import summary data."""

    def format(self, data: Any) -> None:
        """Format and display import summary with basic data."""
        # Basic format implementation for compatibility
        self.console.print(f"Import summary: {data}")

    def format_import_result(
        self,
        response: Any,
        file_path: str,
        user_id: str,
        import_format: str,
        validate_only: bool = False,
    ) -> None:
        """Format and display detailed import summary."""
        table = self.create_table()
        table.add_column("Metric", style="dim")
        table.add_column("Value", style="cyan")

        table.add_row("File", str(file_path))
        table.add_row("Format", import_format.title())
        table.add_row("User ID", user_id)
        table.add_row("Items Processed", str(response.items_processed))

        if not validate_only:
            table.add_row("Items Imported", str(response.items_imported))
            table.add_row("Items Skipped", str(response.items_skipped))
            table.add_row("Success Rate", f"{response.success_rate:.1f}%")

        if response.processing_time_seconds:
            table.add_row("Processing Time", f"{response.processing_time_seconds:.2f}s")

        title = f"{'Validation' if validate_only else 'Import'} Summary:"
        self.console.print(f"\n📋 [bold]{title}[/bold]")
        self.console.print(table)
