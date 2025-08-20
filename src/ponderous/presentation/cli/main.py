"""
Main CLI entry point for the refactored command structure.

This module assembles all commands and groups into the main CLI application.
"""

import sys
from pathlib import Path

import click

from ponderous import __version__

from .base import CONTEXT_SETTINGS, PonderousContext, console
from .commands.collection import collection_commands
from .commands.config import config_commands
from .commands.discovery import discovery_commands
from .commands.edhrec import edhrec_commands
from .commands.recommendations import recommendation_commands
from .commands.testing import testing_commands
from .groups.user import user_group


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
            from ponderous.shared.config import PonderousConfig

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


def register_commands(cli_group: click.Group) -> None:
    """Register all commands and groups with the main CLI."""

    # Register command groups
    cli_group.add_command(user_group)

    # Register individual commands
    for command in collection_commands:
        cli_group.add_command(command)

    for command in discovery_commands:
        cli_group.add_command(command)

    for command in recommendation_commands:
        cli_group.add_command(command)

    for command in edhrec_commands:
        cli_group.add_command(command)

    for command in config_commands:
        cli_group.add_command(command)

    for command in testing_commands:
        cli_group.add_command(command)


# Register all commands
register_commands(cli)


def main() -> None:
    """Main entry point for the CLI application."""
    cli()


if __name__ == "__main__":
    main()
