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
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
)
from rich.table import Table

from ponderous import __version__

# Removed CollectionService import - no longer needed without API sync
from ponderous.infrastructure.database import (
    CardRepositoryImpl,
    CollectionRepository,
    CommanderRepositoryImpl,
    get_database_connection,
)
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
        ponderous import-collection --file collection.csv --user-id myuser
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

    # Import required components (RecommendationService available for future integration)

    # Get database connection and repositories
    db_connection = None
    try:
        db_connection = get_database_connection()
        commander_repo = CommanderRepositoryImpl(db_connection)

        # Initialize repositories for commander discovery
        # RecommendationService available for future integration

        # Get commander recommendations using our new system
        console.print("\n🔍 [bold]Analyzing commanders...[/bold]")

        # Parse color filter
        color_filter = None
        if kwargs["colors"]:
            color_filter = list(kwargs["colors"].replace(",", "").upper())

        # Get recommendations using the new buildability system
        recommendations = commander_repo.get_recommendations_for_collection(
            user_id=kwargs["user_id"],
            color_preferences=color_filter,
            budget_max=kwargs["budget_max"],
            min_completion=kwargs["min_completion"],
            limit=kwargs["limit"],
        )

        if not recommendations:
            console.print(
                "[yellow]⚠️  No commanders found matching criteria. Try lowering --min-completion or run 'ponderous update-edhrec' first.[/yellow]"
            )
            return

        # Display results
        console.print(
            f"\n✨ [bold green]Found {len(recommendations)} buildable commanders![/bold green]"
        )

        # Create results table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Rank", style="dim", width=4)
        table.add_column("Commander", style="cyan", min_width=20)
        table.add_column("Colors", style="bright_blue", width=6)
        table.add_column("Buildability", style="green", width=12)
        table.add_column("Cards Owned", style="yellow", width=11)
        table.add_column("Missing $", style="red", width=10)
        table.add_column("Power", style="magenta", width=6)

        for i, rec in enumerate(recommendations, 1):
            # Format data
            colors = "".join(rec.color_identity) if rec.color_identity else "C"
            buildability = f"{rec.completion_percentage:.1%}"
            cards_owned = f"{rec.owned_cards}/{rec.total_cards}"
            missing_value = f"${rec.missing_cards_value:.0f}"
            power = f"{rec.power_level:.1f}"

            table.add_row(
                str(i),
                rec.commander_name,
                colors,
                buildability,
                cards_owned,
                missing_value,
                power,
            )

        console.print(table)

        # Show summary
        console.print("\n📊 [bold]Summary:[/bold]")
        console.print(
            f"   • Best match: [cyan]{recommendations[0].commander_name}[/cyan] ({recommendations[0].completion_percentage:.1%} buildable)"
        )
        if len(recommendations) > 1:
            console.print(
                f"   • Total investment needed: [red]${sum(r.missing_cards_value for r in recommendations[:3]):.0f}[/red] (top 3)"
            )

        return  # Skip the old filtering logic below

        # OLD CODE - keeping for reference but skipping execution
        filtered_commanders = []
        for commander in []:
            # Apply color filter
            if color_filter:
                commander_colors = set(commander.color_identity)
                filter_colors = set(color_filter)
                if not filter_colors.issubset(commander_colors):
                    continue

            # Apply budget filter
            if kwargs["budget_max"] and commander.avg_deck_price > kwargs["budget_max"]:
                continue
            if kwargs["budget_min"] and commander.avg_deck_price < kwargs["budget_min"]:
                continue

            # Apply power level filter
            if kwargs["power_min"] and commander.power_level < kwargs["power_min"]:
                continue
            if kwargs["power_max"] and commander.power_level > kwargs["power_max"]:
                continue

            # Apply popularity filter
            if (
                kwargs["popularity_min"]
                and commander.total_decks < kwargs["popularity_min"]
            ):
                continue

            # Apply salt score filter
            if (
                kwargs["salt_score_max"]
                and commander.salt_score > kwargs["salt_score_max"]
            ):
                continue

            filtered_commanders.append(commander)

        # Limit results
        filtered_commanders = filtered_commanders[: kwargs["limit"]]

        # Create output table
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Rank", style="dim", width=4)
        table.add_column("Commander", style="cyan")
        table.add_column("Colors", width=8)
        table.add_column("Decks", style="yellow", justify="right")
        table.add_column("Price", style="green", justify="right")
        table.add_column("Power", style="blue", justify="center")
        table.add_column("Salt", style="red", justify="center")

        if not filtered_commanders:
            console.print(
                "[yellow]⚠️  No commanders match your criteria. Try adjusting your filters.[/yellow]"
            )
            return

        # Populate table with real data
        for i, commander in enumerate(filtered_commanders, 1):
            # Format color identity
            colors = commander.color_identity_str if commander.color_identity else "C"

            # Format deck count
            deck_count = f"{commander.total_decks:,}"

            # Format price
            price = f"${commander.avg_deck_price:.0f}"

            # Format power level
            power = f"{commander.power_level:.1f}"

            # Format salt score
            salt = f"{commander.salt_score:.1f}"

            table.add_row(
                str(i),
                commander.name,
                colors,
                deck_count,
                price,
                power,
                salt,
            )

        console.print(table)

        # Show summary
        console.print("\n📊 [bold]Results Summary:[/bold]")
        console.print(
            f"   • Found: [cyan]{len(filtered_commanders)}[/cyan] commanders matching criteria"
        )
        console.print(
            f"   • Total in database: [yellow]{commander_repo.get_commander_stats()['total_commanders']}[/yellow] commanders"
        )

        if kwargs["output_format"] == "json":
            # TODO: Implement JSON output
            console.print("\n[yellow]JSON output format not yet implemented[/yellow]")
        elif kwargs["output_format"] == "csv":
            # TODO: Implement CSV output
            console.print("\n[yellow]CSV output format not yet implemented[/yellow]")

    except Exception as e:
        console.print(f"\n[red]❌ Commander discovery failed: {e}[/red]")
        if ctx.obj.debug:
            console.print_exception()
    finally:
        if db_connection:
            db_connection.close()


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

    # Get database connection and repository
    db_connection = get_database_connection()
    repository = CollectionRepository(db_connection)

    try:
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

        summary_table = Table(show_header=True, header_style="bold magenta")
        summary_table.add_column("Metric", style="dim")
        summary_table.add_column("Value", style="cyan")

        summary_table.add_row("Total Cards", str(summary["total_cards"]))
        summary_table.add_row("Unique Cards", str(summary["unique_cards"]))
        summary_table.add_row("Sets Represented", str(summary["sets_represented"]))
        summary_table.add_row("Foil Cards", str(summary["foil_cards"]))

        if summary.get("last_import"):
            summary_table.add_row("Last Import", str(summary["last_import"])[:19])

        console.print(summary_table)

        # Show condition breakdown if available
        if summary.get("conditions") and summary["conditions"]:
            console.print("\n🎯 [bold]Condition Breakdown:[/bold]")
            condition_table = Table(show_header=True, header_style="bold green")
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
            language_table = Table(show_header=True, header_style="bold blue")
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
            entries_table = Table(show_header=True, header_style="bold yellow")
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
            history_table = Table(show_header=True, header_style="bold purple")
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
        db_connection.close()


@cli.command("update-edhrec")
@click.option(
    "--commanders-file",
    type=click.Path(exists=True, path_type=Path),
    help="File containing list of commanders to update",
)
@click.option("--popular-only", is_flag=True, help="Update only popular commanders")
@click.option("--limit", default=100, type=int, help="Maximum commanders to update")
@click.option(
    "--paginate", is_flag=True, help="Use Playwright pagination to get more commanders"
)
@click.option(
    "--max-pages", default=5, type=int, help="Maximum pages to load when paginating"
)
@click.option(
    "--visible", is_flag=True, help="Run browser in visible mode (for debugging)"
)
@click.pass_context
@handle_exception
def update_edhrec(
    ctx: click.Context,
    commanders_file: Path | None,
    popular_only: bool,
    limit: int,
    paginate: bool,
    max_pages: int,
    visible: bool,
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

    if paginate:
        console.print(f"Mode: [green]Pagination[/green] (max {max_pages} pages)")
        if visible:
            console.print("Browser: [yellow]Visible mode[/yellow] (for debugging)")
        else:
            console.print("Browser: [cyan]Headless mode[/cyan]")
    else:
        console.print(f"Limit: [yellow]{limit}[/yellow] commanders")

    # Import required components
    try:
        from ponderous.domain.models.commander import Commander
        from ponderous.infrastructure.database.repositories.commander_repository_impl import (
            CommanderRepositoryImpl,
        )
        from ponderous.infrastructure.edhrec.scraper import EDHRECScraper
    except ImportError as e:
        console.print(f"[red]Error importing required modules: {e}[/red]")
        return

    async def run_update() -> None:
        """Run the EDHREC update asynchronously."""
        db_connection = None
        commander_repo = None

        try:
            # Get database connection and repository
            db_connection = get_database_connection()
            commander_repo = CommanderRepositoryImpl(db_connection)

            console.print("\n🔍 [bold]Scraping commanders from EDHREC...[/bold]")

            # Create progress display
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                console=console,
            ) as progress:
                scrape_task = progress.add_task(
                    "Fetching commander data...", total=limit
                )

                async with EDHRECScraper() as scraper:
                    # Handle commanders file
                    if commanders_file:
                        console.print(
                            f"[yellow]Reading commanders from file: {commanders_file}[/yellow]"
                        )
                        # TODO: Implement file-based commander list reading
                        console.print(
                            "[yellow]⚠️  File-based updates not yet implemented[/yellow]"
                        )
                        return

                    # Scrape commanders - use pagination if requested
                    if paginate:
                        progress.update(
                            scrape_task,
                            description=f"Using pagination (max {max_pages} pages)...",
                        )
                        edhrec_commanders = await scraper.get_paginated_commanders(
                            max_pages=max_pages, headless=not visible
                        )
                    else:
                        edhrec_commanders = await scraper.get_popular_commanders(
                            limit=limit
                        )

                    progress.update(
                        scrape_task,
                        advance=len(edhrec_commanders),
                        description="Converting to domain models...",
                    )

                    # Convert EDHREC commanders to domain commanders
                    domain_commanders = []
                    for edhrec_commander in edhrec_commanders:
                        try:
                            # Convert color identity string to list
                            color_list = (
                                list(edhrec_commander.color_identity)
                                if edhrec_commander.color_identity != "C"
                                else []
                            )

                            # Generate card_id from URL slug (EDHREC standard format)
                            card_id = f"edhrec_{edhrec_commander.url_slug}"

                            domain_commander = Commander(
                                name=edhrec_commander.name,
                                card_id=card_id,
                                color_identity=color_list,
                                total_decks=edhrec_commander.total_decks,
                                popularity_rank=edhrec_commander.popularity_rank,
                                avg_deck_price=edhrec_commander.avg_deck_price,
                                salt_score=edhrec_commander.salt_score,
                                power_level=edhrec_commander.power_level,
                            )
                            domain_commanders.append(domain_commander)
                        except Exception as e:
                            console.print(
                                f"[yellow]Warning: Failed to convert commander {edhrec_commander.name}: {e}[/yellow]"
                            )
                            continue

                    progress.update(
                        scrape_task, description="Storing commanders to database..."
                    )

                    # Store commanders to database
                    stored_count = 0
                    for commander in domain_commanders:
                        try:
                            commander_repo.store(commander)
                            stored_count += 1
                        except Exception as e:
                            console.print(
                                f"[yellow]Warning: Failed to store {commander.name}: {e}[/yellow]"
                            )
                            continue

                    # Store deck composition data for each commander
                    progress.update(
                        scrape_task, description="Scraping deck composition data..."
                    )
                    cards_stored_total = 0

                    for commander in domain_commanders:
                        try:
                            # Scrape and store deck data for the commander
                            cards_stored = await scraper.scrape_and_store_deck_data(
                                commander.name, archetype="default", budget_range="mid"
                            )
                            cards_stored_total += cards_stored

                            progress.update(
                                scrape_task,
                                description=f"Stored deck data for {commander.name} ({cards_stored} cards)",
                            )

                        except Exception as e:
                            console.print(
                                f"[yellow]Warning: Failed to store deck data for {commander.name}: {e}[/yellow]"
                            )
                            continue

                    progress.update(
                        scrape_task, completed=limit, description="Update complete!"
                    )

            # Success summary
            console.print("\n✅ [bold green]EDHREC Update Complete![/bold green]")
            console.print("📊 [bold]Results:[/bold]")
            console.print(
                f"   • Scraped: [cyan]{len(edhrec_commanders)}[/cyan] commanders"
            )
            console.print(f"   • Stored: [green]{stored_count}[/green] commanders")
            console.print(
                f"   • Card inclusion data: [magenta]{cards_stored_total}[/magenta] cards stored"
            )

            if stored_count < len(edhrec_commanders):
                skipped = len(edhrec_commanders) - stored_count
                console.print(
                    f"   • Skipped: [yellow]{skipped}[/yellow] commanders (conversion/storage errors)"
                )

        except Exception as e:
            console.print(f"\n[red]❌ EDHREC update failed: {e}[/red]")
            if ctx.obj.debug:
                console.print_exception()
        finally:
            if db_connection:
                db_connection.close()

    # Run the async function
    import asyncio

    asyncio.run(run_update())


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


@cli.command("test-cards")
@click.option("--add-samples", is_flag=True, help="Add sample MTG cards to database")
@click.option("--search", type=str, help="Search for cards by partial name")
@click.option("--limit", default=10, type=int, help="Maximum number of results")
@click.pass_context
@handle_exception
def test_cards(
    ctx: click.Context,  # noqa: ARG001
    add_samples: bool,
    search: str | None,
    limit: int,  # noqa: ARG001
) -> None:
    """
    🃏 Test card repository functionality.

    Add sample cards or search existing cards to test the normalized card database.
    """
    console.print("🃏 [bold blue]Card Repository Test[/bold blue]")

    # Get database connection and repository
    db_connection = get_database_connection()
    card_repo = CardRepositoryImpl(db_connection)

    try:
        if add_samples:
            console.print("\n📥 [bold]Adding Sample Cards...[/bold]")

            # Import card model
            from ponderous.domain.models.card import Card

            # Create sample MTG cards
            sample_cards = [
                Card(
                    card_id="lightning_bolt_lea",
                    name="Lightning Bolt",
                    mana_cost="{R}",
                    cmc=1,
                    color_identity=["R"],
                    type_line="Instant",
                    oracle_text="Lightning Bolt deals 3 damage to any target.",
                    rarity="common",
                    set_code="LEA",
                    collector_number="1",
                    price_usd=25.00,
                ),
                Card(
                    card_id="sol_ring_lea",
                    name="Sol Ring",
                    mana_cost="{1}",
                    cmc=1,
                    color_identity=[],
                    type_line="Artifact",
                    oracle_text="{T}: Add {C}{C}.",
                    rarity="uncommon",
                    set_code="LEA",
                    collector_number="2",
                    price_usd=150.00,
                ),
                Card(
                    card_id="edgar_markov",
                    name="Edgar Markov",
                    mana_cost="{3}{R}{W}{B}",
                    cmc=6,
                    color_identity=["R", "W", "B"],
                    type_line="Legendary Creature — Vampire Knight",
                    oracle_text="Eminence — Whenever you cast another Vampire spell, if Edgar Markov is in the command zone or on the battlefield, create a 1/1 black Vampire creature token.",
                    power="4",
                    toughness="4",
                    rarity="mythic",
                    set_code="C17",
                    collector_number="36",
                    price_usd=25.00,
                ),
                Card(
                    card_id="mana_crypt",
                    name="Mana Crypt",
                    mana_cost="{0}",
                    cmc=0,
                    color_identity=[],
                    type_line="Artifact",
                    oracle_text="At the beginning of your upkeep, flip a coin. If you lose the flip, Mana Crypt deals 3 damage to you.\n{T}: Add {C}{C}.",
                    rarity="mythic",
                    set_code="EMA",
                    collector_number="225",
                    price_usd=200.00,
                ),
            ]

            stored_count, skipped_count = card_repo.store_batch(sample_cards)
            console.print(
                f"[green]✓[/green] Stored {stored_count} cards, skipped {skipped_count}"
            )

            # Show stats
            stats = card_repo.get_card_stats()
            console.print(
                f"[cyan]Database now contains {stats['total_cards']} total cards, {stats['unique_names']} unique names[/cyan]"
            )

        if search:
            console.print(f"\n🔍 [bold]Searching for '{search}'...[/bold]")

            results = card_repo.search_by_partial_name(search, limit)

            if results:
                # Create results table
                table = Table(show_header=True, header_style="bold magenta")
                table.add_column("Name", style="cyan")
                table.add_column("Type", style="dim")
                table.add_column("Mana Cost", style="yellow")
                table.add_column("Set", style="green")
                table.add_column("Price", justify="right", style="blue")
                table.add_column("Colors", style="magenta")

                for card in results:
                    colors = (
                        "".join(card.color_identity) if card.color_identity else "C"
                    )
                    price = f"${card.price_usd:.2f}" if card.price_usd else "N/A"

                    table.add_row(
                        card.name,
                        card.type_line or "Unknown",
                        card.mana_cost or "{0}",
                        card.set_code or "UNK",
                        price,
                        colors,
                    )

                console.print(table)
                console.print(f"\n[dim]Found {len(results)} cards[/dim]")
            else:
                console.print(f"[yellow]No cards found matching '{search}'[/yellow]")

        # Show commanders if no specific action
        if not add_samples and not search:
            console.print("\n👑 [bold]Available Commanders:[/bold]")
            commanders = card_repo.get_commanders()

            if commanders:
                commander_table = Table(show_header=True, header_style="bold purple")
                commander_table.add_column("Commander", style="cyan")
                commander_table.add_column("Colors", style="magenta")
                commander_table.add_column("Mana Cost", style="yellow")
                commander_table.add_column("Set", style="green")

                for commander in commanders:
                    colors = (
                        "".join(commander.color_identity)
                        if commander.color_identity
                        else "C"
                    )
                    commander_table.add_row(
                        commander.name,
                        colors,
                        commander.mana_cost or "Unknown",
                        commander.set_code or "UNK",
                    )

                console.print(commander_table)
            else:
                console.print(
                    "[yellow]No commanders found. Use --add-samples to add some sample cards.[/yellow]"
                )

            # Show general stats
            stats = card_repo.get_card_stats()
            console.print("\n📊 [bold]Card Database Stats:[/bold]")
            console.print(f"Total Cards: {stats['total_cards']}")
            console.print(f"Unique Names: {stats['unique_names']}")
            if stats.get("sets_count"):
                console.print(f"Sets: {stats['sets_count']}")

    except Exception as e:
        console.print(f"[red]Error testing cards: {e}[/red]")
    finally:
        db_connection.close()


@cli.command("scrape-edhrec")
@click.option("--limit", default=10, type=int, help="Number of commanders to scrape")
@click.option("--test-mode", is_flag=True, help="Test scraper without storing data")
@click.pass_context
@handle_exception
def scrape_edhrec(
    ctx: click.Context,  # noqa: ARG001
    limit: int,
    test_mode: bool,  # noqa: ARG001
) -> None:
    """
    🌐 Scrape commander data from EDHREC.

    Extract popular commanders and their statistics from EDHREC for deck recommendations.
    """
    console.print("🌐 [bold blue]EDHREC Commander Scraper[/bold blue]")

    # Import EDHREC scraper
    try:
        from ponderous.infrastructure.edhrec import EDHRECScraper
    except ImportError as e:
        console.print(f"[red]Error importing EDHREC scraper: {e}[/red]")
        return

    async def run_scraper() -> None:
        """Run the scraper asynchronously."""
        db_connection = None
        commander_repo = None

        try:
            if not test_mode:
                db_connection = get_database_connection()
                commander_repo = CommanderRepositoryImpl(db_connection)

            console.print(
                f"\n🔍 [bold]Scraping {limit} commanders from EDHREC...[/bold]"
            )

            # Create progress display
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
            ) as progress:
                task = progress.add_task("Fetching commander data...", total=None)

                async with EDHRECScraper() as scraper:
                    commanders = await scraper.get_popular_commanders(limit=limit)

                progress.update(task, description="Storing to database...")

                # Store commanders to database if not in test mode
                if not test_mode and commanders and commander_repo:
                    # Convert EDHREC commanders to domain commanders
                    from ponderous.domain.models.commander import Commander

                    domain_commanders = []

                    for edhrec_commander in commanders:
                        # Convert color identity string to list
                        color_list = (
                            list(edhrec_commander.color_identity)
                            if edhrec_commander.color_identity != "C"
                            else []
                        )

                        domain_commander = Commander(
                            name=edhrec_commander.name,
                            card_id=f"edhrec_{edhrec_commander.url_slug}",
                            color_identity=color_list,
                            total_decks=edhrec_commander.total_decks,
                            popularity_rank=edhrec_commander.popularity_rank,
                            avg_deck_price=edhrec_commander.avg_deck_price,
                            salt_score=edhrec_commander.salt_score,
                            power_level=edhrec_commander.power_level,
                        )
                        domain_commanders.append(domain_commander)

                    # Store batch
                    stored_count, skipped_count = commander_repo.store_batch(
                        domain_commanders
                    )
                    progress.update(
                        task, description=f"Stored {stored_count} commanders..."
                    )

                progress.update(task, description="Processing results...")

                # Create mock result for display
                from datetime import datetime

                from ponderous.infrastructure.edhrec.models import EDHRECScrapingResult

                result = EDHRECScrapingResult(
                    success=True,
                    commanders_found=len(commanders),
                    decks_found=0,
                    cards_found=0,
                    processing_time_seconds=0.0,  # Will be calculated
                    errors=[],
                    warnings=[],
                    scraped_at=datetime.now(),
                )

                # Display results
                console.print("\n📊 [bold]Scraping Results:[/bold]")

                results_table = Table(show_header=True, header_style="bold green")
                results_table.add_column("Metric", style="dim")
                results_table.add_column("Value", style="cyan")

                results_table.add_row(
                    "Success", "✅ Yes" if result.success else "❌ No"
                )
                results_table.add_row("Commanders Found", str(result.commanders_found))
                results_table.add_row(
                    "Processing Time", f"{result.processing_time_seconds:.1f}s"
                )
                results_table.add_row(
                    "Scraped At", result.scraped_at.strftime("%Y-%m-%d %H:%M:%S")
                )

                console.print(results_table)

                if result.has_errors:
                    console.print("\n❌ [bold red]Errors:[/bold red]")
                    for error in result.errors:
                        console.print(f"  • {error}")

                if result.warnings:
                    console.print("\n⚠️  [bold yellow]Warnings:[/bold yellow]")
                    for warning in result.warnings:
                        console.print(f"  • {warning}")

                if result.success and result.commanders_found > 0:
                    console.print(
                        f"\n✅ [green]Successfully scraped {result.commanders_found} commanders![/green]"
                    )

                    if test_mode:
                        console.print(
                            "[yellow]Test mode: No data was stored to database[/yellow]"
                        )
                    else:
                        console.print("[cyan]Data stored to commander database[/cyan]")
                else:
                    console.print(
                        "\n❌ [red]Scraping failed or no commanders found[/red]"
                    )

        except Exception as e:
            console.print(f"[red]Error during scraping: {e}[/red]")
        finally:
            if db_connection:
                db_connection.close()

    # Run the async scraper
    try:
        asyncio.run(run_scraper())
    except KeyboardInterrupt:
        console.print("\n[yellow]Scraping cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Scraping failed: {e}[/red]")


@cli.command("recommend-commanders")
@click.option("--user-id", required=True, help="User ID for collection analysis")
@click.option("--colors", help="Preferred color identity (e.g., 'BG', 'WUB')")
@click.option("--limit", default=10, type=int, help="Maximum number of recommendations")
@click.option(
    "--min-buildability", default=1.0, type=float, help="Minimum buildability score"
)
@click.pass_context
@handle_exception
def recommend_commanders(
    ctx: click.Context,  # noqa: ARG001
    user_id: str,
    colors: str | None,
    limit: int,
    min_buildability: float,
) -> None:
    """
    🎯 Get commander recommendations based on your collection.

    Analyze your collection to find which commanders you can build with high completion rates.
    """
    console.print("🎯 [bold blue]Commander Recommendations[/bold blue]")
    console.print(f"User: [cyan]{user_id}[/cyan]")
    if colors:
        console.print(f"Color Preference: [magenta]{colors}[/magenta]")

    # Get database connections and repositories
    db_connection = get_database_connection()

    try:
        card_repo = CardRepositoryImpl(db_connection)
        commander_repo = CommanderRepositoryImpl(db_connection)
        collection_repo = CollectionRepository(db_connection)

        # Import recommendation service
        from ponderous.application.services.recommendation_service import (
            RecommendationService,
        )

        recommendation_service = RecommendationService(
            card_repo=card_repo,
            commander_repo=commander_repo,
            collection_repo=collection_repo,
        )

        # Parse color preferences
        color_list = list(colors.upper()) if colors else None

        console.print(
            "\n🔍 [bold]Analyzing collection for buildable commanders...[/bold]"
        )

        # Get recommendations
        recommendations = recommendation_service.get_commander_recommendations(
            user_id=user_id,
            color_preferences=color_list,
            min_completion=0.05,  # Very low threshold for initial test
            limit=limit,
        )

        if not recommendations:
            console.print(
                f"[yellow]No commander recommendations found for user {user_id}[/yellow]"
            )
            console.print("This could mean:")
            console.print("  • No collection data found")
            console.print("  • No commanders in card database")
            console.print(
                "  • Try importing your collection first with 'import-collection'"
            )
            console.print("  • Try adding sample cards with 'test-cards --add-samples'")
            return

        # Display recommendations
        console.print(
            f"\n👑 [bold]Top {len(recommendations)} Commander Recommendations:[/bold]"
        )

        recommendations_table = Table(show_header=True, header_style="bold purple")
        recommendations_table.add_column("Commander", style="cyan")
        recommendations_table.add_column("Colors", style="magenta")
        recommendations_table.add_column("Completion", justify="right", style="green")
        recommendations_table.add_column(
            "Buildability", justify="right", style="yellow"
        )
        recommendations_table.add_column("Est. Cost", justify="right", style="blue")
        recommendations_table.add_column("Archetype", style="dim")

        for rec in recommendations:
            colors_str = "".join(rec.color_identity) if rec.color_identity else "C"
            completion_str = f"{rec.completion_percentage:.1%}"
            buildability_str = f"{rec.buildability_score:.1f}/10"
            cost_str = f"${rec.avg_deck_price:.0f}"

            recommendations_table.add_row(
                rec.commander_name,
                colors_str,
                completion_str,
                buildability_str,
                cost_str,
                rec.archetype,
            )

        console.print(recommendations_table)

        # Show collection stats
        collection_summary = collection_repo.get_user_collection_summary(user_id)
        console.print("\n📊 [bold]Collection Overview:[/bold]")
        console.print(f"Total Cards: {collection_summary['total_cards']}")
        console.print(f"Unique Cards: {collection_summary['unique_cards']}")

        # Show buildable commanders
        buildable = [
            r for r in recommendations if r.buildability_score >= min_buildability
        ]
        if buildable:
            console.print(
                f"\n✨ [bold green]Highly Buildable ({len(buildable)}):[/bold green]"
            )
            for rec in buildable:
                console.print(
                    f"  • {rec.commander_name} ({rec.buildability_score:.1f}/10 buildability)"
                )
        else:
            console.print(
                f"\n💡 [yellow]No commanders meet minimum buildability of {min_buildability:.1f}/10[/yellow]"
            )
            console.print(
                "Consider lowering the threshold or importing more cards to your collection."
            )

    except Exception as e:
        console.print(f"[red]Error generating recommendations: {e}[/red]")
        import traceback

        if ctx.obj.debug:
            console.print(f"[dim]{traceback.format_exc()}[/dim]")
    finally:
        db_connection.close()


def main() -> None:
    """Main entry point for the CLI application."""
    cli()


if __name__ == "__main__":
    main()
