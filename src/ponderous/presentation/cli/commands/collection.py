"""
Collection management commands.

Commands for importing, analyzing, and managing MTG card collections.
"""

import asyncio
import sys
from pathlib import Path

import click

from ponderous.application.services import CollectionAnalyzer
from ponderous.infrastructure.database import (
    CollectionRepository,
    CommanderRepositoryImpl,
)
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
@click.option("--show-value", is_flag=True, help="Show collection value analysis")
@click.option("--show-synergy", is_flag=True, help="Show synergy overlap analysis")
@click.option("--show-investment", is_flag=True, help="Show investment recommendations")
@click.option("--budget", type=float, help="Budget for investment recommendations")
@click.option("--limit", default=10, type=int, help="Maximum number of entries to show")
@click.pass_context
@handle_exception
def analyze_collection(
    ctx: click.Context,  # noqa: ARG001
    user_id: str,
    show_themes: bool,
    show_gaps: bool,
    show_value: bool,
    show_synergy: bool,
    show_investment: bool,
    budget: float | None,
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

        # Advanced analytics using CollectionAnalyzer
        if any([show_themes, show_gaps, show_value, show_synergy, show_investment]):
            console.print("\n🔬 [bold blue]Advanced Analytics[/bold blue]")

            try:
                # Initialize analyzer with repositories
                commander_repo = CommanderRepositoryImpl(db_connection)
                analyzer = CollectionAnalyzer(repository, commander_repo)

                # Get comprehensive analysis
                analysis = analyzer.analyze_collection(user_id)

                # Show collection value analysis
                if show_value:
                    console.print(
                        "\n💰 [bold green]Collection Value Analysis:[/bold green]"
                    )
                    value_metrics = analyzer.calculate_collection_value(user_id)

                    value_table = commands.summary_formatter.create_table(
                        header_style="bold green"
                    )
                    value_table.add_column("Metric", style="dim")
                    value_table.add_column("Value", style="green")

                    value_table.add_row(
                        "Total Cards", str(value_metrics["total_cards"])
                    )
                    value_table.add_row(
                        "Unique Cards", str(value_metrics["unique_cards"])
                    )
                    value_table.add_row(
                        "Estimated Total Value", f"${value_metrics['total_value']:.2f}"
                    )
                    value_table.add_row(
                        "Average Card Value", f"${value_metrics['average_value']:.2f}"
                    )

                    console.print(value_table)

                    # Show most valuable cards
                    valuable_cards = analyzer.identify_most_valuable_cards(
                        user_id, limit=5
                    )
                    if valuable_cards:
                        console.print("\n💎 [bold]Most Valuable Cards:[/bold]")
                        for card in valuable_cards:
                            console.print(
                                f"   • {card['card_name']} (×{card['quantity']}) - ${card['estimated_value']:.2f}"
                            )

                # Show theme compatibility analysis
                if show_themes:
                    console.print("\n🎭 [bold magenta]Theme Analysis:[/bold magenta]")

                    # Color distribution
                    console.print("\n🌈 [bold]Color Distribution:[/bold]")
                    for color, count in analysis.color_distribution.items():
                        percentage = (
                            (count / analysis.total_cards * 100)
                            if analysis.total_cards > 0
                            else 0
                        )
                        console.print(
                            f"   • {color}: {count} cards ({percentage:.1f}%)"
                        )

                    console.print(
                        f"\n⭐ [bold]Strongest Colors:[/bold] {', '.join(analysis.strongest_colors[:3])}"
                    )

                    # Archetype affinities
                    if analysis.archetype_affinity:
                        console.print("\n🏗️  [bold]Archetype Affinities:[/bold]")
                        for archetype, score in sorted(
                            analysis.archetype_affinity.items(),
                            key=lambda x: x[1],
                            reverse=True,
                        ):
                            console.print(
                                f"   • {archetype}: {score:.1%} compatibility"
                            )

                    # Theme support
                    if analysis.theme_support:
                        console.print("\n🎲 [bold]Theme Support:[/bold]")
                        for theme, score in sorted(
                            analysis.theme_support.items(),
                            key=lambda x: x[1],
                            reverse=True,
                        ):
                            if score > 0.05:  # Only show themes with >5% support
                                console.print(f"   • {theme}: {score:.1%} support")

                # Show synergy overlaps
                if show_synergy:
                    console.print("\n🔗 [bold cyan]Synergy Overlaps:[/bold cyan]")
                    synergy_groups = analyzer.find_synergy_overlaps(user_id)

                    if synergy_groups:
                        for group in synergy_groups:
                            console.print(
                                f"\n   🎯 [bold]{group['theme']}[/bold] (Score: {group['synergy_score']:.2f})"
                            )
                            console.print(
                                f"      Cards: {', '.join(group['cards'][:5])}"
                            )
                            if len(group["cards"]) > 5:
                                console.print(
                                    f"      ... and {len(group['cards']) - 5} more"
                                )
                            console.print(
                                f"      Commander overlap: {group['commander_overlap']} decks"
                            )
                    else:
                        console.print("   No significant synergy overlaps detected")

                # Show collection gaps
                if show_gaps:
                    console.print("\n🕳️  [bold yellow]Collection Gaps:[/bold yellow]")
                    gaps = analyzer.identify_collection_gaps(user_id)

                    if gaps:
                        for gap in gaps:
                            priority_color = (
                                "red"
                                if gap["priority"] == "high"
                                else "yellow"
                                if gap["priority"] == "medium"
                                else "dim"
                            )
                            console.print(
                                f"\n   ⚠️  [bold {priority_color}]{gap['gap_type']}[/bold {priority_color}]"
                            )
                            console.print(f"      {gap['description']}")
                            console.print(f"      💡 {gap['suggestion']}")
                    else:
                        console.print("   No significant collection gaps identified")

                    # Show missing staples
                    if analysis.missing_staples:
                        console.print("\n📋 [bold]Missing Common Staples:[/bold]")
                        for staple in analysis.missing_staples[:10]:
                            console.print(f"   • {staple}")

                # Show investment recommendations
                if show_investment:
                    investment_budget = budget or 100.0  # Default $100 budget
                    console.print(
                        f"\n💸 [bold green]Investment Recommendations[/bold green] (${investment_budget:.0f} budget)"
                    )

                    recommendations = analyzer.recommend_card_purchases(
                        user_id, investment_budget
                    )

                    if recommendations:
                        total_cost = 0.0
                        for rec in recommendations:
                            console.print(
                                f"\n   💳 [bold]{rec['card_name']}[/bold] - ${rec['estimated_price']:.2f}"
                            )
                            console.print(
                                f"      Impact: {rec['impact_score']}/10 - {rec['reason']}"
                            )
                            total_cost += rec["estimated_price"]

                        console.print(
                            f"\n   📊 [bold]Total Cost:[/bold] ${total_cost:.2f} of ${investment_budget:.2f} budget"
                        )
                        console.print(
                            f"   💰 [bold]Remaining:[/bold] ${investment_budget - total_cost:.2f}"
                        )
                    else:
                        console.print(
                            "   No recommendations within budget or collection already optimized"
                        )

            except Exception as e:
                console.print(f"\n[red]Error performing advanced analytics: {e}[/red]")
                console.print("[dim]Falling back to basic analysis mode[/dim]")

    except Exception as e:
        console.print(f"[red]Error analyzing collection: {e}[/red]")
    finally:
        commands.close_db_connection()


# Register commands for import
collection_commands = [import_collection, analyze_collection]
