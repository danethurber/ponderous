"""
CLI interface for Ponderous - MTG Commander deck recommendation tool.

This module provides the command-line interface for analyzing MTG collections
and discovering buildable Commander decks using Click framework and Rich output.
"""

import asyncio
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any, TypeVar

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ponderous import __version__
from ponderous.application.services import CollectionService
from ponderous.infrastructure.importers import ImportRequest, MoxfieldCSVImporter
from ponderous.shared.config import PonderousConfig, get_config
from ponderous.shared.exceptions import PonderousError

# Use unlimited width to prevent path truncation in tests
console = Console(width=None)


class PonderousContext:
    """CLI context object to pass data between commands."""

    def __init__(self) -> None:
        self.config = get_config()
        self.debug = self.config.debug
        self.verbose = False


CONTEXT_SETTINGS = {
    "help_option_names": ["-h", "--help"],
    "max_content_width": 120,
}


F = TypeVar("F", bound=Callable[..., Any])


def handle_exception(func: F) -> F:
    """Decorator to handle exceptions gracefully in CLI commands."""

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


@click.group(context_settings=CONTEXT_SETTINGS, invoke_without_command=True)
@click.option(
    "--debug",
    is_flag=True,
    help="Enable debug mode with detailed error information.",
)
@click.option(
    "--verbose",
    "-v",
    is_flag=True,
    help="Enable verbose output.",
)
@click.option(
    "--config-file",
    type=click.Path(exists=True, path_type=Path),
    help="Path to configuration file.",
)
@click.version_option(version=__version__, prog_name="ponderous")
@click.pass_context
def cli(
    ctx: click.Context, debug: bool, verbose: bool, config_file: Path | None
) -> None:
    """
    🎯 Ponderous - Thoughtful analysis of your MTG collection to discover buildable Commander decks.

    Analyze your Magic: The Gathering collection against comprehensive EDHREC statistics
    to find which Commander decks you can build with minimal additional investment.

    Examples:
        ponderous sync-collection --username myuser --source moxfield
        ponderous discover-commanders --user-id myuser --colors BG --budget-max 300
        ponderous recommend-decks "Meren of Clan Nel Toth" --user-id myuser
    """
    ctx.ensure_object(PonderousContext)
    ctx.obj.debug = debug or ctx.obj.debug
    ctx.obj.verbose = verbose

    if config_file:
        try:
            ctx.obj.config = PonderousConfig.from_file(config_file)
            if verbose:
                console.print(
                    f"[green]✓[/green] Loaded configuration from {config_file}"
                )
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to load config file: {e}")
            sys.exit(1)

    if ctx.invoked_subcommand is None:
        click.echo(ctx.get_help())


@cli.group()
@click.pass_context
def user(ctx: click.Context) -> None:
    """👤 User and collection management commands."""
    pass


@user.command("list")
@click.pass_context
@handle_exception
def list_users(ctx: click.Context) -> None:  # noqa: ARG001
    """List all registered users."""
    console.print("🔍 [bold blue]Listing Users[/bold blue]")

    # TODO: Implement user listing logic
    # This will be implemented when the user repository is available
    console.print("[yellow]⚠️  User management not yet implemented[/yellow]")
    console.print("Coming soon: List all users with collection sync status")


@user.command("stats")
@click.argument("user_id")
@click.pass_context
@handle_exception
def user_stats(ctx: click.Context, user_id: str) -> None:  # noqa: ARG001
    """Show statistics for a specific user."""
    console.print(f"📊 [bold blue]User Statistics for {user_id}[/bold blue]")

    # TODO: Implement user stats logic
    console.print("[yellow]⚠️  User statistics not yet implemented[/yellow]")
    console.print(
        "Coming soon: Collection size, value, sync history, and analysis stats"
    )


@cli.command("sync-collection")
@click.option("--username", required=True, help="Username on the collection platform")
@click.option(
    "--source",
    default="moxfield",
    type=click.Choice(["moxfield"], case_sensitive=False),
    help="Collection source platform",
)
@click.option("--force", is_flag=True, help="Force resync even if recently updated")
@click.pass_context
@handle_exception
def sync_collection(
    ctx: click.Context,  # noqa: ARG001
    username: str,
    source: str,
    force: bool,
) -> None:
    """
    🔄 Sync your card collection from external platforms.

    Downloads and analyzes your card collection from supported platforms
    like Moxfield to enable deck recommendations.

    Example:
        ponderous sync-collection --username myuser --source moxfield
    """
    console.print("🔄 [bold blue]Syncing Collection[/bold blue]")
    console.print(f"Username: [cyan]{username}[/cyan]")
    console.print(f"Source: [cyan]{source.title()}[/cyan]")

    if force:
        console.print("[yellow]Force sync enabled - ignoring cache[/yellow]")

    async def _run_sync() -> None:
        """Run the async sync operation."""
        collection_service = CollectionService()

        try:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Connecting to API...", total=None)

                # Validate username format first
                if not collection_service.validate_username_format(username, source):
                    raise PonderousError(
                        f"Invalid username format for {source}: {username}"
                    )

                progress.update(task, description="Downloading collection data...")

                # Perform the actual sync
                response = await collection_service.sync_user_collection(
                    username=username,
                    source=source,
                    force_refresh=force,
                    include_profile=True,
                )

                progress.update(task, description="Processing and validating...")

                if response.success:
                    progress.update(task, description="✅ Sync completed successfully")

                    # Display success summary
                    console.print()
                    console.print(
                        "🎉 [bold green]Collection sync completed![/bold green]"
                    )
                    console.print(
                        f"📊 {response.unique_cards} unique cards ({response.total_cards} total)"
                    )

                    if response.sync_duration_seconds:
                        console.print(
                            f"⏱️  Completed in {response.sync_duration_seconds:.1f} seconds"
                        )

                    # Show collection summary table
                    summary_table = Table(show_header=True, header_style="bold magenta")
                    summary_table.add_column("Metric", style="dim")
                    summary_table.add_column("Value", style="cyan")

                    summary_table.add_row("Username", response.username)
                    summary_table.add_row("Source", response.source.title())
                    summary_table.add_row("Unique Cards", str(response.unique_cards))
                    summary_table.add_row("Total Cards", str(response.total_cards))
                    summary_table.add_row(
                        "Items Processed", str(response.items_processed)
                    )
                    if response.sync_duration_seconds:
                        summary_table.add_row(
                            "Duration", f"{response.sync_duration_seconds:.1f}s"
                        )

                    console.print("\n📋 [bold]Sync Summary:[/bold]")
                    console.print(summary_table)

                else:
                    progress.update(task, description="❌ Sync failed")
                    console.print()
                    console.print("[bold red]❌ Collection sync failed![/bold red]")
                    if response.error_message:
                        console.print(f"Error: {response.error_message}")
                    raise PonderousError("Collection sync failed")

        except PonderousError:
            raise
        except Exception as e:
            console.print(
                f"\n[bold red]❌ Unexpected error during sync:[/bold red] {e}"
            )
            raise PonderousError(f"Collection sync failed: {e}") from e

    # Run the async sync operation
    try:
        asyncio.run(_run_sync())
    except KeyboardInterrupt:
        console.print("\n[yellow]⚠️  Sync cancelled by user[/yellow]")
        sys.exit(1)


@cli.command("import-collection")
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
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
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
                    if validate_only:
                        console.print(
                            "🎉 [bold green]File validation completed![/bold green]"
                        )
                    else:
                        console.print(
                            "🎉 [bold green]Collection import completed![/bold green]"
                        )

                    console.print(f"📊 {response.items_processed} items processed")

                    if not validate_only:
                        console.print(f"📥 {response.items_imported} items imported")

                    if response.processing_time_seconds:
                        console.print(
                            f"⏱️  Completed in {response.processing_time_seconds:.2f} seconds"
                        )

                    # Show import summary table
                    summary_table = Table(show_header=True, header_style="bold magenta")
                    summary_table.add_column("Metric", style="dim")
                    summary_table.add_column("Value", style="cyan")

                    summary_table.add_row("File", str(file_path.name))
                    summary_table.add_row("Format", import_format.title())
                    summary_table.add_row("User ID", user_id)
                    summary_table.add_row(
                        "Items Processed", str(response.items_processed)
                    )

                    if not validate_only:
                        summary_table.add_row(
                            "Items Imported", str(response.items_imported)
                        )
                        summary_table.add_row(
                            "Items Skipped", str(response.items_skipped)
                        )
                        summary_table.add_row(
                            "Success Rate", f"{response.success_rate:.1f}%"
                        )

                    if response.processing_time_seconds:
                        summary_table.add_row(
                            "Processing Time",
                            f"{response.processing_time_seconds:.2f}s",
                        )

                    console.print(
                        f"\n📋 [bold]{'Validation' if validate_only else 'Import'} Summary:[/bold]"
                    )
                    console.print(summary_table)

                    # Show warnings if any
                    if response.has_warnings:
                        console.print("\n⚠️  [bold yellow]Warnings:[/bold yellow]")
                        for warning in response.warnings:
                            console.print(f"   • {warning}")

                else:
                    progress.update(task, description="❌ Import failed")
                    console.print()
                    console.print("[bold red]❌ Collection import failed![/bold red]")

                    # Show errors
                    if response.has_errors:
                        console.print("\n💥 [bold red]Errors:[/bold red]")
                        for error in response.errors:
                            console.print(f"   • {error}")

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


@cli.command("discover-commanders")
@click.option("--user-id", required=True, help="User identifier")
@click.option("--colors", help="Color combinations: W,U,B,R,G or WU,BR,etc.")
@click.option("--exclude-colors", help="Colors to exclude")
@click.option("--budget-min", type=float, help="Minimum deck cost")
@click.option("--budget-max", type=float, help="Maximum deck cost")
@click.option(
    "--budget-bracket",
    type=click.Choice(["budget", "mid", "high", "cedh"], case_sensitive=False),
    help="Budget bracket filter",
)
@click.option(
    "--archetype",
    help="Comma-separated archetypes: aggro,control,combo,midrange",
)
@click.option("--exclude-archetype", help="Archetypes to exclude")
@click.option("--themes", help="Preferred themes: tribal,artifacts,graveyard,etc.")
@click.option("--exclude-themes", help="Themes to avoid")
@click.option("--power-min", type=float, help="Minimum power level (1-10)")
@click.option("--power-max", type=float, help="Maximum power level (1-10)")
@click.option("--popularity-min", type=int, help="Minimum EDHREC deck count")
@click.option("--salt-score-max", type=float, help="Maximum salt score tolerance")
@click.option("--win-rate-min", type=float, help="Minimum competitive win rate")
@click.option(
    "--min-completion",
    default=0.7,
    type=float,
    help="Minimum collection completion",
)
@click.option(
    "--sort-by",
    default="completion",
    help="Sort criteria: completion,buildability,popularity,power-level,budget",
)
@click.option(
    "--format",
    "output_format",
    default="table",
    type=click.Choice(["table", "json", "csv"], case_sensitive=False),
    help="Output format",
)
@click.option("--limit", default=20, type=int, help="Maximum number of results")
@click.option("--show-missing", is_flag=True, help="Include missing cards analysis")
@click.pass_context
@handle_exception
def discover_commanders(ctx: click.Context, **kwargs: Any) -> None:  # noqa: ARG001
    """
    🔍 Discover optimal commanders based on your collection.

    Analyzes your collection to find commanders you can build most easily,
    considering owned cards, budget constraints, and deck preferences.

    Examples:
        # Find Golgari commanders under $300
        ponderous discover-commanders --user-id myuser --colors BG --budget-max 300

        # Find competitive control decks
        ponderous discover-commanders --user-id myuser --archetype control --power-min 8

        # Find popular tribal commanders
        ponderous discover-commanders --user-id myuser --themes tribal --popularity-min 2000
    """
    console.print("🔍 [bold blue]Commander Discovery[/bold blue]")
    console.print(f"User: [cyan]{kwargs['user_id']}[/cyan]")

    # Show active filters
    active_filters = []
    if kwargs["colors"]:
        active_filters.append(f"Colors: {kwargs['colors']}")
    if kwargs["budget_bracket"]:
        active_filters.append(f"Budget: {kwargs['budget_bracket'].title()}")
    if kwargs["archetype"]:
        active_filters.append(f"Archetype: {kwargs['archetype']}")
    if kwargs["min_completion"] != 0.7:
        active_filters.append(f"Min Completion: {kwargs['min_completion']:.1%}")

    if active_filters:
        console.print("🎛️  [bold]Active Filters:[/bold]")
        for filter_desc in active_filters:
            console.print(f"   • {filter_desc}")

    # TODO: Implement commander discovery logic
    console.print("[yellow]⚠️  Commander discovery not yet implemented[/yellow]")

    # Show example output structure
    console.print("\n📋 [bold]Expected Output Format:[/bold]")

    table = Table(show_header=True, header_style="bold magenta")
    table.add_column("Rank", style="dim", width=4)
    table.add_column("Commander", style="cyan")
    table.add_column("Colors", width=8)
    table.add_column("Budget", style="green")
    table.add_column("Archetype", style="blue")
    table.add_column("Owned", style="yellow")
    table.add_column("Completion", style="green", justify="right")
    table.add_column("Cost", style="red", justify="right")

    # Sample data for demonstration
    sample_data = [
        ("1", "Meren of Clan Nel Toth", "BG", "Mid", "Combo", "78/89", "87.6%", "$67"),
        (
            "2",
            "Atraxa, Praetors' Voice",
            "WUBG",
            "High",
            "Control",
            "84/98",
            "85.7%",
            "$245",
        ),
        ("3", "The Gitrog Monster", "BG", "Mid", "Combo", "71/84", "84.5%", "$89"),
    ]

    for row in sample_data:
        table.add_row(*row)

    console.print(table)
    console.print(
        "\n💡 [italic]Coming soon: Full implementation with your actual collection data[/italic]"
    )


@cli.command("discover")
@click.option("--user-id", required=True, help="User identifier")
@click.option(
    "--budget-bracket",
    type=click.Choice(["budget", "mid", "high", "cedh"], case_sensitive=False),
    help="Budget bracket filter",
)
@click.option(
    "--min-completion",
    default=0.75,
    type=float,
    help="Minimum collection completion",
)
@click.option("--limit", default=10, type=int, help="Maximum number of results")
@click.pass_context
@handle_exception
def discover_quick(
    ctx: click.Context,  # noqa: ARG001
    user_id: str,
    budget_bracket: str,
    min_completion: float,
    limit: int,  # noqa: ARG001
) -> None:
    """
    ⚡ Quick commander discovery with common filters.

    Simplified version of discover-commanders with sensible defaults
    for quick analysis.
    """
    console.print("⚡ [bold blue]Quick Commander Discovery[/bold blue]")
    console.print(f"User: [cyan]{user_id}[/cyan]")
    console.print(f"Budget: [green]{(budget_bracket or 'Any').title()}[/green]")
    console.print(f"Min Completion: [yellow]{min_completion:.1%}[/yellow]")

    # TODO: Implement quick discovery logic
    console.print("[yellow]⚠️  Quick discovery not yet implemented[/yellow]")
    console.print("Coming soon: Streamlined commander recommendations")


@cli.command("recommend-decks")
@click.argument("commander_name")
@click.option("--user-id", required=True, help="User identifier")
@click.option(
    "--budget",
    type=click.Choice(["budget", "mid", "high", "cedh"], case_sensitive=False),
    help="Budget category filter",
)
@click.option(
    "--min-completion",
    default=0.7,
    type=float,
    help="Minimum completion percentage",
)
@click.option(
    "--sort-by",
    default="buildability",
    type=click.Choice(["completion", "buildability", "budget"], case_sensitive=False),
    help="Sort criteria",
)
@click.option("--limit", default=10, type=int, help="Maximum number of recommendations")
@click.pass_context
@handle_exception
def recommend_decks(
    ctx: click.Context,  # noqa: ARG001
    commander_name: str,
    user_id: str,
    budget: str | None,
    min_completion: float,
    sort_by: str,
    limit: int,  # noqa: ARG001
) -> None:
    """
    🎯 Get deck recommendations for a specific commander.

    Analyzes different deck variants for the specified commander based on
    your collection, budget preferences, and completion requirements.

    Examples:
        ponderous recommend-decks "Meren of Clan Nel Toth" --user-id myuser
        ponderous recommend-decks "Atraxa, Praetors' Voice" --user-id myuser --budget mid
    """
    console.print("🎯 [bold blue]Deck Recommendations[/bold blue]")
    console.print(f"Commander: [magenta]{commander_name}[/magenta]")
    console.print(f"User: [cyan]{user_id}[/cyan]")

    if budget:
        console.print(f"Budget Filter: [green]{budget.title()}[/green]")
    console.print(f"Min Completion: [yellow]{min_completion:.1%}[/yellow]")
    console.print(f"Sort by: [blue]{sort_by.title()}[/blue]")

    # TODO: Implement deck recommendation logic
    console.print("\n[yellow]⚠️  Deck recommendations not yet implemented[/yellow]")

    # Show example output
    console.print(f"\n🎯 [bold]Sample Recommendations for {commander_name}:[/bold]")

    panel_content = """
📋 Reanimator Combo (Control)
   💰 Budget: Mid ($450)
   ✅ Completion: 87.3%
   📊 Buildability Score: 8.7/10
   🃏 Cards: 78/89 owned
   💸 Missing Value: $67

📋 +1/+1 Counters (Midrange)
   💰 Budget: Budget ($180)
   ✅ Completion: 92.1%
   📊 Buildability Score: 8.2/10
   🃏 Cards: 82/89 owned
   💸 Missing Value: $23
   ⚠️  Missing 2 high-impact cards
    """

    panel = Panel(
        panel_content.strip(),
        title="Deck Variants",
        title_align="left",
        border_style="green",
    )
    console.print(panel)
    console.print(
        "\n💡 [italic]Coming soon: Full analysis with your collection data[/italic]"
    )


@cli.command("deck-details")
@click.argument("commander_name")
@click.option("--user-id", required=True, help="User identifier")
@click.option("--archetype", help="Specific archetype to analyze")
@click.option("--budget", help="Specific budget category")
@click.option(
    "--show-missing", is_flag=True, help="Show detailed missing cards analysis"
)
@click.pass_context
@handle_exception
def deck_details(
    ctx: click.Context,  # noqa: ARG001
    commander_name: str,
    user_id: str,
    archetype: str | None,
    budget: str | None,
    show_missing: bool,  # noqa: ARG001
) -> None:
    """
    🔍 Get detailed analysis for specific deck configuration.

    Shows comprehensive breakdown of a specific commander deck variant,
    including owned cards, missing cards, and upgrade recommendations.
    """
    console.print("🔍 [bold blue]Detailed Deck Analysis[/bold blue]")
    console.print(f"Commander: [magenta]{commander_name}[/magenta]")
    console.print(f"User: [cyan]{user_id}[/cyan]")

    if archetype:
        console.print(f"Archetype: [blue]{archetype}[/blue]")
    if budget:
        console.print(f"Budget: [green]{budget}[/green]")

    # TODO: Implement detailed deck analysis
    console.print("[yellow]⚠️  Detailed deck analysis not yet implemented[/yellow]")
    console.print(
        "Coming soon: Comprehensive deck breakdown with card-by-card analysis"
    )


@cli.command("analyze-collection")
@click.option("--user-id", required=True, help="User identifier")
@click.option("--show-themes", is_flag=True, help="Show theme compatibility analysis")
@click.option(
    "--show-gaps", is_flag=True, help="Show collection gaps and recommendations"
)
@click.pass_context
@handle_exception
def analyze_collection(
    ctx: click.Context,  # noqa: ARG001
    user_id: str,
    show_themes: bool,
    show_gaps: bool,  # noqa: ARG001
) -> None:
    """
    📊 Analyze collection strengths and provide strategic insights.

    Provides comprehensive analysis of your collection including color distribution,
    archetype affinities, missing staples, and investment recommendations.
    """
    console.print("📊 [bold blue]Collection Analysis[/bold blue]")
    console.print(f"User: [cyan]{user_id}[/cyan]")

    # TODO: Implement collection analysis
    console.print("[yellow]⚠️  Collection analysis not yet implemented[/yellow]")
    console.print(
        "Coming soon: Deep insights into your collection strengths and opportunities"
    )

    if show_themes:
        console.print("\n🎭 [bold]Theme Analysis:[/bold] Coming soon")
    if show_gaps:
        console.print("\n🕳️  [bold]Collection Gaps:[/bold] Coming soon")


@cli.command("update-edhrec")
@click.option(
    "--commanders-file",
    type=click.Path(exists=True, path_type=Path),
    help="File containing list of commanders to update",
)
@click.option("--popular-only", is_flag=True, help="Update only popular commanders")
@click.option("--limit", default=100, type=int, help="Maximum commanders to update")
@click.pass_context
@handle_exception
def update_edhrec(
    ctx: click.Context,  # noqa: ARG001
    commanders_file: Path | None,
    popular_only: bool,
    limit: int,
) -> None:
    """
    🔄 Update EDHREC data for commanders and deck statistics.

    Downloads and processes EDHREC data for specified commanders or
    popular commanders to enable accurate deck recommendations.
    """
    console.print("🔄 [bold blue]Updating EDHREC Data[/bold blue]")

    if commanders_file:
        # Use click.echo for long paths to avoid Rich truncation in tests
        click.echo(f"Source: {commanders_file}")
    elif popular_only:
        console.print("Source: [cyan]Popular commanders only[/cyan]")

    console.print(f"Limit: [yellow]{limit}[/yellow] commanders")

    # TODO: Implement EDHREC data update
    console.print("[yellow]⚠️  EDHREC data updates not yet implemented[/yellow]")
    console.print("Coming soon: Comprehensive EDHREC scraping and data processing")


@cli.command("edhrec-stats")
@click.argument("commander_name")
@click.pass_context
@handle_exception
def edhrec_stats(ctx: click.Context, commander_name: str) -> None:  # noqa: ARG001
    """Show EDHREC statistics for a specific commander."""
    console.print(f"📈 [bold blue]EDHREC Statistics for {commander_name}[/bold blue]")

    # TODO: Implement EDHREC stats display
    console.print("[yellow]⚠️  EDHREC statistics not yet implemented[/yellow]")
    console.print("Coming soon: Detailed commander statistics from EDHREC")


@cli.command("config")
@click.option("--show", is_flag=True, help="Show current configuration")
@click.option("--init", is_flag=True, help="Initialize default configuration file")
@click.option(
    "--file",
    "config_file",
    type=click.Path(path_type=Path),
    help="Configuration file path",
)
@click.pass_context
@handle_exception
def config_cmd(
    ctx: click.Context, show: bool, init: bool, config_file: Path | None
) -> None:
    """
    ⚙️ Manage Ponderous configuration.

    View current settings or initialize a configuration file with default values.
    """
    if show:
        console.print("⚙️ [bold blue]Current Configuration[/bold blue]")

        config = ctx.obj.config

        # Create configuration display
        config_text = f"""
[bold]Database:[/bold]
  Path: {config.database.path}
  Memory Mode: {config.database.memory}
  Threads: {config.database.threads}

[bold]Moxfield API:[/bold]
  Base URL: {config.moxfield.base_url}
  Timeout: {config.moxfield.timeout}s
  Rate Limit: {config.moxfield.rate_limit} req/s

[bold]EDHREC Scraping:[/bold]
  Base URL: {config.edhrec.base_url}
  Timeout: {config.edhrec.timeout}s
  Rate Limit: {config.edhrec.rate_limit} req/s

[bold]Analysis:[/bold]
  Min Completion Threshold: {config.analysis.min_completion_threshold:.1%}
  Max Commanders: {config.analysis.max_commanders_to_analyze}
  Cache Results: {config.analysis.cache_results}

[bold]Logging:[/bold]
  Level: {config.logging.level}
  File: {config.logging.file_path or "Console only"}

[bold]Application:[/bold]
  Debug Mode: {config.debug}
  Config Directory: {config.config_dir}
        """.strip()

        panel = Panel(
            config_text,
            title="Configuration",
            title_align="left",
            border_style="blue",
        )
        console.print(panel)

    elif init:
        config_path = config_file or (ctx.obj.config.config_dir / "config.toml")
        console.print(f"🔧 Initializing configuration at [cyan]{config_path}[/cyan]")

        try:
            ctx.obj.config.save_to_file(config_path)
            console.print(f"[green]✓[/green] Configuration saved to {config_path}")
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to save configuration: {e}")
            sys.exit(1)

    else:
        console.print(
            "Use --show to view current config or --init to create default config file"
        )


def main() -> None:
    """Main entry point for the CLI application."""
    cli()


if __name__ == "__main__":
    main()
