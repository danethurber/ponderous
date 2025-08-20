"""
Testing and development commands.

Commands used for testing functionality and development workflows.
"""

import asyncio

import click
from rich.table import Table

from ponderous.application.services.recommendation_service import RecommendationService
from ponderous.domain.models.card import Card
from ponderous.infrastructure.database import (
    CardRepositoryImpl,
    CollectionRepository,
    CommanderRepositoryImpl,
)
from ponderous.infrastructure.edhrec import EDHRECScraper
from ponderous.infrastructure.edhrec.models import EDHRECScrapingResult

from ..base import (
    DatabaseMixin,
    common_limit_option,
    console,
    create_simple_progress,
    handle_exception,
)


class TestingCommands(DatabaseMixin):
    """Testing and development command implementations."""

    def __init__(self) -> None:
        super().__init__()


@click.command("test-cards")
@click.option("--add-samples", is_flag=True, help="Add sample MTG cards to database")
@click.option("--search", type=str, help="Search for cards by partial name")
@common_limit_option
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

    commands = TestingCommands()

    try:
        db_connection = commands.get_db_connection()
        card_repo = CardRepositoryImpl(db_connection)

        if add_samples:
            console.print("\n📥 [bold]Adding Sample Cards...[/bold]")

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
        commands.close_db_connection()


@click.command("scrape-edhrec")
@common_limit_option
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

    commands = TestingCommands()

    async def run_scraper() -> None:
        """Run the scraper asynchronously."""
        try:
            if not test_mode:
                db_connection = commands.get_db_connection()
                commander_repo = CommanderRepositoryImpl(db_connection)

            console.print(
                f"\n🔍 [bold]Scraping {limit} commanders from EDHREC...[/bold]"
            )

            # Create progress display
            with create_simple_progress() as progress:
                task = progress.add_task("Fetching commander data...", total=None)

                async with EDHRECScraper() as scraper:
                    commanders = await scraper.get_popular_commanders(limit=limit)

                progress.update(task, description="Storing to database...")

                # Store commanders to database if not in test mode
                if not test_mode and commanders and "commander_repo" in locals():
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
            commands.close_db_connection()

    # Run the async scraper
    try:
        asyncio.run(run_scraper())
    except KeyboardInterrupt:
        console.print("\n[yellow]Scraping cancelled by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Scraping failed: {e}[/red]")


@click.command("recommend-commanders")
@click.option("--user-id", required=True, help="User ID for collection analysis")
@click.option("--colors", help="Preferred color identity (e.g., 'BG', 'WUB')")
@common_limit_option
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

    commands = TestingCommands()

    try:
        db_connection = commands.get_db_connection()
        card_repo = CardRepositoryImpl(db_connection)
        commander_repo = CommanderRepositoryImpl(db_connection)
        collection_repo = CollectionRepository(db_connection)

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
        commands.close_db_connection()


# Register commands for import
testing_commands = [test_cards, scrape_edhrec, recommend_commanders]
