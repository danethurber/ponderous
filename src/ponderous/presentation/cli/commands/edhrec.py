"""
EDHREC integration commands.

Commands for updating and displaying EDHREC commander statistics.
"""

import asyncio
from pathlib import Path

import click

from ponderous.domain.models.commander import Commander
from ponderous.infrastructure.database.repositories.commander_repository_impl import (
    CommanderRepositoryImpl,
)
from ponderous.infrastructure.edhrec.scraper import EDHRECScraper

from ..base import (
    DatabaseMixin,
    console,
    create_progress,
    handle_exception,
    success_message,
    warning_message,
)


class EDHRECCommands(DatabaseMixin):
    """EDHREC integration command implementations."""

    def __init__(self) -> None:
        super().__init__()


@click.command("update-edhrec")
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

    commands = EDHRECCommands()

    async def run_update() -> None:
        """Run the EDHREC update asynchronously."""
        try:
            # Get database connection and repository
            db_connection = commands.get_db_connection()
            commander_repo = CommanderRepositoryImpl(db_connection)

            console.print("\n🔍 [bold]Scraping commanders from EDHREC...[/bold]")

            # Create progress display
            with create_progress() as progress:
                scrape_task = progress.add_task(
                    "Fetching commander data...", total=limit
                )

                async with EDHRECScraper() as scraper:
                    # Handle commanders file
                    if commanders_file:
                        console.print(
                            f"[yellow]Reading commanders from file: {commanders_file}[/yellow]"
                        )
                        warning_message("File-based updates not yet implemented")
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
            success_message("EDHREC Update Complete!")
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
            commands.close_db_connection()

    # Run the async function
    asyncio.run(run_update())


@click.command("edhrec-stats")
@click.argument("commander_name")
@click.pass_context
@handle_exception
def edhrec_stats(ctx: click.Context, commander_name: str) -> None:  # noqa: ARG001
    """Show EDHREC statistics for a specific commander."""
    console.print(f"📈 [bold blue]EDHREC Statistics for {commander_name}[/bold blue]")

    # TODO: Implement EDHREC stats display
    warning_message("EDHREC statistics not yet implemented")
    console.print("Coming soon: Detailed commander statistics from EDHREC")


# Register commands for import
edhrec_commands = [update_edhrec, edhrec_stats]
