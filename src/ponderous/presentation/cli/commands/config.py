"""
Configuration management commands.

Commands for managing Ponderous configuration settings.
"""

import sys
from pathlib import Path

import click
from rich.panel import Panel

from ..base import console, handle_exception


@click.command("config")
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


# Register commands for import
config_commands = [config_cmd]
