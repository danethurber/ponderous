"""
User management command group.

Commands for managing users and their collection data.
"""

import click

from ..base import console, handle_exception


@click.group()
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


# Register group for import
user_group = user
