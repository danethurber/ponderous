"""
Collection management commands.

Commands for importing, analyzing, and managing MTG card collections.
"""

import asyncio
import sys
from pathlib import Path

import click

from ponderous.infrastructure.database import CollectionRepository
from ponderous.infrastructure.importers import ImportRequest, MoxfieldCSVImporter
from ponderous.shared.exceptions import PonderousError

from ...formatters.progress import ProgressFormatter
from ...formatters.table import CollectionSummaryFormatter, ImportSummaryFormatter
from ..base import (
    DatabaseMixin,
    console,
    create_simple_progress,
    handle_exception,
)


class CollectionCommands(DatabaseMixin):
    """Collection management command implementations."""

    def __init__(self) -> None:
        super().__init__()
        self.progress_formatter = ProgressFormatter(console)
        self.summary_formatter = CollectionSummaryFormatter(console)
        self.import_formatter = ImportSummaryFormatter(console)


@click.command("import-collection")
@click.option(
    "--file",
    "file_path",
    required=True,
    type=click.Path(exists=True, path_type=Path),
    help="Path to collection file (CSV format)",
)
@click.option("--user-id", required=True, help="User identifier for this collection")
@click.option(
    "--format",
    "import_format",
    default="moxfield_csv",
    type=click.Choice(["moxfield_csv"], case_sensitive=False),
    help="Import file format",
)
@click.option(
    "--validate-only",
    is_flag=True,
    help="Validate file format without importing data",
)
@click.option(
    "--skip-duplicates",
    is_flag=True,
    default=True,
    help="Skip duplicate entries (default: enabled)",
)
@click.pass_context
@handle_exception
def import_collection(
    ctx: click.Context,  # noqa: ARG001
    file_path: Path,
    user_id: str,
    import_format: str,
    validate_only: bool,
    skip_duplicates: bool,
) -> None:
    """
    📂 Import your card collection from a file.

    Import collection data from exported files (CSV format) to enable deck
    recommendations. Currently supports Moxfield CSV exports.

    Examples:
        ponderous import-collection --file my_collection.csv --user-id myuser
        ponderous import-collection --file collection.csv --user-id myuser --validate-only
    """
    console.print("📂 [bold blue]Importing Collection[/bold blue]")
    console.print(f"File: [cyan]{file_path}[/cyan]")
    console.print(f"User ID: [cyan]{user_id}[/cyan]")
    console.print(f"Format: [cyan]{import_format.title()}[/cyan]")

    if validate_only:
        console.print("[yellow]Validation mode - no data will be imported[/yellow]")

    formatter = ProgressFormatter(console)
    import_formatter = ImportSummaryFormatter(console)

    async def _run_import() -> None:
        """Run the async import operation."""
        # Create appropriate importer based on format
        if import_format.lower() == "moxfield_csv":
            importer = MoxfieldCSVImporter()
        else:
            raise PonderousError(f"Unsupported import format: {import_format}")

        # Verify file format is supported
        if not importer.supports_format(file_path):
            raise PonderousError(
                f"File format not supported by {import_format} importer: {file_path.suffix}"
            )

        try:
            with create_simple_progress() as progress:
                task = progress.add_task("Validating file format...", total=None)

                # Create import request
                request = ImportRequest(
                    file_path=file_path,
                    user_id=user_id,
                    source=f"{import_format}_import",
                    validate_only=validate_only,
                    skip_duplicates=skip_duplicates,
                )

                progress.update(task, description="Reading and parsing file...")

                # Perform the import
                response = await importer.import_collection(request)

                if validate_only:
                    progress.update(task, description="✅ File validation completed")
                else:
                    progress.update(
                        task, description="✅ Import completed successfully"
                    )

                if response.success:
                    # Display success summary
                    console.print()
                    formatter.format_import_progress(response)

                    # Show import summary table
                    import_formatter.format_import_result(
                        response,
                        str(file_path.name),
                        user_id,
                        import_format,
                        validate_only,
                    )

                    # Show warnings if any
                    formatter.format_warnings(response)

                else:
                    progress.update(task, description="❌ Import failed")
                    console.print()
                    console.print("[bold red]❌ Collection import failed![/bold red]")

                    # Show errors
                    formatter.format_errors(response)
                    raise PonderousError("Collection import failed")

        except Exception as e:
            if not isinstance(e, PonderousError):
                console.print(
                    f"\n[bold red]❌ Unexpected error during import:[/bold red] {e}"
                )
                raise PonderousError(f"Collection import failed: {e}") from e
            raise

    # Run the async import operation
    try:
        asyncio.run(_run_import())
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Import cancelled by user[/yellow]")
        sys.exit(1)


@click.command("analyze-collection")
@click.option("--user-id", required=True, help="User identifier")
@click.option("--show-themes", is_flag=True, help="Show theme compatibility analysis")
@click.option(
    "--show-gaps", is_flag=True, help="Show collection gaps and recommendations"
)
@click.option("--limit", default=10, type=int, help="Maximum number of entries to show")
@click.pass_context
@handle_exception
def analyze_collection(
    ctx: click.Context,  # noqa: ARG001
    user_id: str,
    show_themes: bool,
    show_gaps: bool,
    limit: int,
) -> None:
    """
    📊 Analyze collection strengths and provide strategic insights.

    Provides comprehensive analysis of your collection including color distribution,
    archetype affinities, missing staples, and investment recommendations.
    """
    console.print("📊 [bold blue]Collection Analysis[/bold blue]")
    console.print(f"User: [cyan]{user_id}[/cyan]")

    commands = CollectionCommands()

    try:
        db_connection = commands.get_db_connection()
        repository = CollectionRepository(db_connection)

        # Get collection summary
        summary = repository.get_user_collection_summary(user_id)

        if summary["total_cards"] == 0:
            console.print(
                f"\n[yellow]No collection data found for user {user_id}[/yellow]"
            )
            console.print(
                "Use 'ponderous import-collection' to import your collection first."
            )
            return

        # Display collection summary
        console.print("\n📋 [bold]Collection Summary:[/bold]")
        commands.summary_formatter.format(summary)

        # Show condition breakdown if available
        if summary.get("conditions") and summary["conditions"]:
            console.print("\n🎯 [bold]Condition Breakdown:[/bold]")
            condition_table = commands.summary_formatter.create_table(
                header_style="bold green"
            )
            condition_table.add_column("Condition", style="dim")
            condition_table.add_column("Entries", style="cyan")
            condition_table.add_column("Total Cards", style="green")

            for condition, data in summary["conditions"].items():
                condition_table.add_row(
                    condition or "Unknown", str(data["entries"]), str(data["cards"])
                )
            console.print(condition_table)

        # Show language breakdown if multiple languages
        if summary.get("languages") and len(summary["languages"]) > 1:
            console.print("\n🌍 [bold]Language Breakdown:[/bold]")
            language_table = commands.summary_formatter.create_table(
                header_style="bold blue"
            )
            language_table.add_column("Language", style="dim")
            language_table.add_column("Entries", style="cyan")
            language_table.add_column("Total Cards", style="green")

            for language, data in summary["languages"].items():
                language_table.add_row(
                    language, str(data["entries"]), str(data["cards"])
                )
            console.print(language_table)

        # Show sample collection entries
        console.print(f"\n🃏 [bold]Sample Collection (top {limit}):[/bold]")
        collection_entries = repository.get_collection_by_user(user_id, limit=limit)

        if collection_entries:
            entries_table = commands.summary_formatter.create_table(
                header_style="bold yellow"
            )
            entries_table.add_column("Card Name", style="cyan")
            entries_table.add_column("Set", style="dim")
            entries_table.add_column("Qty", justify="right", style="green")
            entries_table.add_column("Condition", style="yellow")
            entries_table.add_column("Foil", justify="center", style="magenta")

            for entry in collection_entries:
                entries_table.add_row(
                    entry["card_name"],
                    entry["set_name"],
                    str(entry["quantity"]),
                    entry["condition"] or "Unknown",
                    "✨" if entry["foil"] else "—",
                )
            console.print(entries_table)

        # Show import history
        import_history = repository.get_import_history(user_id, limit=5)
        if import_history:
            console.print("\n📥 [bold]Recent Import History:[/bold]")
            history_table = commands.summary_formatter.create_table(
                header_style="bold purple"
            )
            history_table.add_column("Date", style="dim")
            history_table.add_column("Format", style="cyan")
            history_table.add_column("Processed", justify="right", style="green")
            history_table.add_column("Imported", justify="right", style="blue")
            history_table.add_column("Success Rate", justify="right", style="yellow")

            for record in import_history:
                history_table.add_row(
                    str(record["created_at"])[:19],
                    record["format"],
                    str(record["items_processed"]),
                    str(record["items_imported"]),
                    f"{record['success_rate']:.1f}%",
                )
            console.print(history_table)

        # Placeholder for future features
        if show_themes:
            console.print("\n🎭 [bold yellow]Theme Analysis:[/bold yellow] Coming soon")
            console.print("   • Tribal synergies analysis")
            console.print("   • Archetype compatibility scoring")
            console.print("   • Color identity recommendations")

        if show_gaps:
            console.print(
                "\n🕳️  [bold yellow]Collection Gaps:[/bold yellow] Coming soon"
            )
            console.print("   • Missing staples identification")
            console.print("   • Budget upgrade suggestions")
            console.print("   • Commander viability analysis")

    except Exception as e:
        console.print(f"[red]Error analyzing collection: {e}[/red]")
    finally:
        commands.close_db_connection()


# Register commands for import
collection_commands = [import_collection, analyze_collection]
