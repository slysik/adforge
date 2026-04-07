"""
CLI entry point for the creative automation pipeline.

Commands:
  generate  — Run the full pipeline on a campaign brief
  validate  — Validate a brief without generating assets
  analyze   — Score and analyze a brief's quality
  providers — List available image generation providers
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
@click.version_option(version="2.0.0", prog_name="adforge")
def cli():
    """AdForge — creative automation for localized social campaigns.

    \b
    Provider chain: Adobe Firefly → DALL-E 3 → Mock (auto-resolved)
    Templates: product_hero | editorial | split_panel | minimal | bold_type
    """
    load_dotenv()


@cli.command()
@click.argument("brief", type=click.Path(exists=True))
@click.option("--input-dir", "-i", default="input_assets", help="Directory with existing assets")
@click.option("--output-dir", "-o", default="output", help="Output directory for generated creatives")
@click.option("--mock", is_flag=True, help="Use mock image generation (no API key needed)")
@click.option("--provider", "-p", type=click.Choice(["firefly", "dalle", "gemini", "mock"]),
              help="Force a specific image provider")
@click.option("--template", "-t",
              type=click.Choice(["product_hero", "editorial", "split_panel", "minimal", "bold_type"]),
              help="Force a specific layout template")
@click.option("--api-key", envvar="OPENAI_API_KEY", help="OpenAI API key (or set OPENAI_API_KEY env)")
@click.option("--no-analysis", is_flag=True, help="Skip brief analysis stage")
@click.option("--no-parallel", is_flag=True, help="Disable parallel hero generation")
@click.option("--workers", "-w", default=4, help="Thread pool size for parallel generation")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
def generate(brief, input_dir, output_dir, mock, provider, template,
             api_key, no_analysis, no_parallel, workers, verbose):
    """Generate campaign creatives from a brief file.

    BRIEF is a YAML or JSON campaign brief file.

    \b
    Examples:
        adforge generate sample_briefs/summer_campaign.yaml --mock
        adforge generate brief.yaml --provider firefly
        adforge generate brief.yaml --template minimal --mock
        adforge generate brief.yaml -p dalle -t editorial
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
        provider_type=provider,
        template=template,
        analyze=not no_analysis,
        parallel=not no_parallel,
        max_workers=workers,
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


@cli.command()
@click.argument("brief", type=click.Path(exists=True))
@click.option("--llm", is_flag=True, help="Augment heuristic analysis with LLM insights")
def analyze(brief: str, llm: bool):
    """Analyze a campaign brief's quality and get recommendations.

    Scores the brief on completeness, clarity, brand strength, and targeting.
    Provides actionable suggestions for improvement.

    BRIEF is a YAML or JSON campaign brief file.

    \b
    Examples:
        adforge analyze sample_briefs/summer_campaign.yaml
        adforge analyze brief.yaml --llm
    """
    from .pipeline import load_brief
    from .analyzer import analyze_brief, print_analysis

    try:
        b = load_brief(brief)
        analysis = analyze_brief(b, use_llm=llm)
        print_analysis(analysis)
    except Exception as exc:
        console.print(f"[red]✗ Analysis failed: {exc}[/red]")
        sys.exit(1)


@cli.command()
def providers():
    """List available image generation providers and their status."""
    from .providers import FireflyProvider, DalleProvider, GeminiProvider, MockProvider

    console.print("\n[bold cyan]━━━ Available Providers ━━━[/bold cyan]\n")

    providers_list = [
        ("Adobe Firefly Services", FireflyProvider(), "firefly",
         "Production — uses Firefly v3 API (generate, expand, fill)"),
        ("OpenAI DALL-E 3", DalleProvider(), "dalle",
         "Development fallback — three fixed sizes, resized to target"),
        ("Google Imagen 4.0", GeminiProvider(), "gemini",
         "Development fallback — native aspect ratios via Gemini API"),
        ("Mock Provider", MockProvider(), "mock",
         "Testing — deterministic procedural images, no API calls"),
    ]

    for name, prov, flag, desc in providers_list:
        available = prov.is_available()
        icon = "[green]✓[/green]" if available else "[red]✗[/red]"
        status = "[green]available[/green]" if available else "[dim]not configured[/dim]"
        console.print(f"  {icon} [bold]{name}[/bold] (--provider {flag})")
        console.print(f"    Status: {status}")
        console.print(f"    Model:  {prov.model_name}")
        console.print(f"    {desc}")
        console.print()

    console.print(
        "[dim]Auto-resolution order: Firefly → Gemini → Mock\n"
        "Set FIREFLY_CLIENT_ID + FIREFLY_CLIENT_SECRET for Firefly.\n"
        "Set GEMINI_API_KEY for Imagen 4.0.\n"
        "Set OPENAI_API_KEY for DALL-E.\n"
        "Use --mock to force mock mode.[/dim]\n"
    )


def main():
    cli()


if __name__ == "__main__":
    main()
