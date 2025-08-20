"""
Commander discovery commands.

Commands for discovering buildable commanders based on collection analysis.
"""

from typing import Any

import click

from ponderous.infrastructure.database import CommanderRepositoryImpl

from ...formatters.table import CommanderRecommendationFormatter
from ..base import (
    BudgetChoice,
    DatabaseMixin,
    OutputFormatChoice,
    common_user_id_option,
    console,
    handle_exception,
    warning_message,
)


class DiscoveryCommands(DatabaseMixin):
    """Commander discovery command implementations."""

    def __init__(self) -> None:
        super().__init__()
        self.recommendation_formatter = CommanderRecommendationFormatter(console)


@click.command("discover-commanders")
@common_user_id_option
@click.option("--colors", help="Color combinations: W,U,B,R,G or WU,BR,etc.")
@click.option("--exclude-colors", help="Colors to exclude")
@click.option("--budget-min", type=float, help="Minimum deck cost")
@click.option("--budget-max", type=float, help="Maximum deck cost")
@click.option("--budget-bracket", type=BudgetChoice, help="Budget bracket filter")
@click.option(
    "--archetype", help="Comma-separated archetypes: aggro,control,combo,midrange"
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
    "--min-completion", default=0.7, type=float, help="Minimum collection completion"
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
    type=OutputFormatChoice,
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

    commands = DiscoveryCommands()

    try:
        db_connection = commands.get_db_connection()
        commander_repo = CommanderRepositoryImpl(db_connection)

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
            warning_message(
                "No commanders found matching criteria. Try lowering --min-completion or run 'ponderous update-edhrec' first."
            )
            return

        # Display results
        console.print(
            f"\n✨ [bold green]Found {len(recommendations)} buildable commanders![/bold green]"
        )
        commands.recommendation_formatter.format(recommendations)

        # Show summary
        console.print("\n📊 [bold]Summary:[/bold]")
        console.print(
            f"   • Best match: [cyan]{recommendations[0].commander_name}[/cyan] ({recommendations[0].completion_percentage:.1%} buildable)"
        )
        if len(recommendations) > 1:
            console.print(
                f"   • Total investment needed: [red]${sum(r.missing_cards_value for r in recommendations[:3]):.0f}[/red] (top 3)"
            )

        # TODO: Implement JSON/CSV output formats
        if kwargs["output_format"] == "json":
            console.print("\n[yellow]JSON output format not yet implemented[/yellow]")
        elif kwargs["output_format"] == "csv":
            console.print("\n[yellow]CSV output format not yet implemented[/yellow]")

    except Exception as e:
        console.print(f"\n[red]❌ Commander discovery failed: {e}[/red]")
        if ctx.obj.debug:
            console.print_exception()
    finally:
        commands.close_db_connection()


@click.command("discover")
@common_user_id_option
@click.option("--budget-bracket", type=BudgetChoice, help="Budget bracket filter")
@click.option(
    "--min-completion", default=0.75, type=float, help="Minimum collection completion"
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

    # TODO: Implement quick discovery logic using the same backend as discover-commanders
    warning_message("Quick discovery not yet implemented")
    console.print("Coming soon: Streamlined commander recommendations")


# Register commands for import
discovery_commands = [discover_commanders, discover_quick]
