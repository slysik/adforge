"""
CLI entry point for the creative automation pipeline.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="adforge")
def cli():
    """AdForge - creative automation for localized social campaigns."""
    load_dotenv()


@cli.command()
@click.argument("brief", type=click.Path(exists=True))
@click.option("--input-dir", "-i", default="input_assets", help="Directory with existing assets")
@click.option("--output-dir", "-o", default="output", help="Output directory for generated creatives")
@click.option("--mock", is_flag=True, help="Use mock image generation (no API key needed)")
@click.option("--api-key", envvar="OPENAI_API_KEY", help="OpenAI API key (or set OPENAI_API_KEY env)")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def generate(brief: str, input_dir: str, output_dir: str, mock: bool, api_key: str, verbose: bool):
    """Generate campaign creatives from a brief file.

    BRIEF is a YAML or JSON campaign brief file.

    Examples:

        python -m src.cli generate sample_briefs/summer_campaign.yaml

        python -m src.cli generate sample_briefs/summer_campaign.yaml --mock

        python -m src.cli generate brief.json -o ./my_output --api-key sk-xxx
    """
    if verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.WARNING)

    from .pipeline import run_pipeline

    result = run_pipeline(
        brief_path=brief,
        input_dir=input_dir,
        output_dir=output_dir,
        mock=mock,
        api_key=api_key,
    )

    if result.failed_count > 0:
        sys.exit(1)


@cli.command()
@click.argument("brief", type=click.Path(exists=True))
def validate(brief: str):
    """Validate a campaign brief file without generating assets.

    BRIEF is a YAML or JSON campaign brief file.
    """
    from .pipeline import load_brief

    try:
        b = load_brief(brief)
        console.print(f"[green]✓ Brief is valid![/green]")
        console.print(f"  Campaign: {b.name}")
        console.print(f"  Products: {len(b.products)}")
        console.print(f"  Ratios:   {len(b.aspect_ratios)}")
        console.print(f"  Languages: {b.languages}")
        total = len(b.products) * len(b.aspect_ratios) * len(b.languages)
        console.print(f"  Will generate: [bold]{total}[/bold] creatives")
    except Exception as exc:
        console.print(f"[red]✗ Validation failed: {exc}[/red]")
        sys.exit(1)


def main():
    cli()


if __name__ == "__main__":
    main()
