"""
Main creative automation pipeline orchestrator.

Stages:
  1. Brief normalization — parse, validate, log
  2. Asset resolution — discover existing heroes or mark for generation
  3. Hero generation — generate missing heroes via GenAI (per-ratio)
  4. Layout rendering — compose final creatives with text, logo, branding
  5. Policy checks — brand compliance + legal checks against rendered output
  6. Reporting — console summary, JSON, HTML
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .models import (
    CampaignBrief, PipelineResult, GeneratedAsset,
    AssetStatus, ComplianceStatus, ComplianceResult,
)
from .generator import ImageGenerator
from .compositor import Compositor, get_translator
from .validator import BrandComplianceChecker, LegalChecker
from .storage import StorageManager
from .report import print_console_report, save_json_report, save_html_report

console = Console()
logger = logging.getLogger("adforge")


# -----------------------------------------------------------------------
# Stage 1: Brief normalization
# -----------------------------------------------------------------------

def load_brief(path: str | Path) -> CampaignBrief:
    """Load and validate a campaign brief from YAML or JSON."""
    p = Path(path)
    text = p.read_text()
    if p.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(text)
    else:
        import json
        data = json.loads(text)

    # Support nested 'campaign' key or flat structure
    if "campaign" in data:
        data = data["campaign"]

    return CampaignBrief(**data)


# -----------------------------------------------------------------------
# Main pipeline
# -----------------------------------------------------------------------

def run_pipeline(
    brief_path: str | Path,
    input_dir: str | Path = "input_assets",
    output_dir: str | Path = "output",
    mock: bool = False,
    api_key: str | None = None,
) -> PipelineResult:
    """Execute the full creative automation pipeline."""
    start = time.time()

    # ── Stage 1: Brief normalization ──────────────────────────────────
    console.print("\n[bold cyan]━━━ AdForge ━━━[/bold cyan]\n")
    brief = load_brief(brief_path)
    console.print(f"[bold]Campaign:[/bold] {brief.name}")
    console.print(f"[bold]Brand:[/bold]    {brief.brand}")
    console.print(f"[bold]Region:[/bold]   {brief.target_region}")
    console.print(f"[bold]Audience:[/bold] {brief.target_audience}")
    console.print(f"[bold]Products:[/bold] {len(brief.products)}")
    console.print(f"[bold]Ratios:[/bold]   {', '.join(r.ratio for r in brief.aspect_ratios)}")
    console.print(f"[bold]Languages:[/bold] {', '.join(brief.languages)}")
    if brief.brand_guidelines.required_disclaimer:
        console.print(f"[bold]Disclaimer:[/bold] {brief.brand_guidelines.required_disclaimer}")
    console.print()

    # ── Initialize components ─────────────────────────────────────────
    storage = StorageManager(input_dir=Path(input_dir), output_dir=Path(output_dir))
    generator = ImageGenerator(api_key=api_key, mock=mock)
    compositor = Compositor(
        brand_colors=brief.brand_guidelines.primary_colors,
        accent_color=brief.brand_guidelines.accent_color,
        font_family=brief.brand_guidelines.font_family,
        logo_path=brief.brand_guidelines.logo_path,
        required_disclaimer=brief.brand_guidelines.required_disclaimer,
    )
    brand_checker = BrandComplianceChecker(
        brand_colors=brief.brand_guidelines.primary_colors,
        logo_path=brief.brand_guidelines.logo_path,
        prohibited_words=brief.brand_guidelines.prohibited_words,
    )
    legal_checker = LegalChecker()
    translator = get_translator()
    translator.clear_warnings()

    result = PipelineResult(campaign_name=brief.name)
    total_tasks = len(brief.products) * len(brief.aspect_ratios) * len(brief.languages)

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Generating creatives…", total=total_tasks)

        for product in brief.products:
            console.print(f"\n[bold white]▸ Product: {product.name}[/bold white]")

            # ── Stage 2: Asset resolution ─────────────────────────────
            existing_hero = storage.find_existing_hero(product.id, product.hero_image)
            hero_status = AssetStatus.REUSED if existing_hero else AssetStatus.GENERATED
            hero_prompt: str | None = None

            if existing_hero:
                existing_hero = storage.copy_hero_to_output(
                    existing_hero, brief.name, product.id,
                )

            if existing_hero is None:
                console.print(f"  [yellow]↳ No existing hero – will generate per ratio[/yellow]")

            # ── Stage 3+4: Hero generation + Layout rendering ─────────
            for ratio in brief.aspect_ratios:
                # Generate or reuse hero for this specific ratio
                hero_path = existing_hero

                if hero_path is None:
                    # Generate hero at the target ratio directly
                    # (avoids the 1:1-cropped-to-everything problem)
                    try:
                        hero_out = storage.hero_output_path(
                            brief.name, product.id, ratio.name,
                        )
                        hero_path, hero_prompt = generator.generate_hero(
                            product_name=product.name,
                            product_description=product.description,
                            keywords=product.keywords,
                            campaign_message=brief.message,
                            target_audience=brief.target_audience,
                            target_region=brief.target_region,
                            brand_name=brief.brand,
                            aspect_ratio=ratio.ratio,
                            output_path=hero_out,
                        )
                        console.print(
                            f"  [green]✓ Hero ({ratio.ratio}): {hero_path}[/green]"
                        )
                    except Exception as exc:
                        console.print(f"  [red]✗ Hero generation failed: {exc}[/red]")
                        hero_status = AssetStatus.FAILED
                        result.warnings.append(
                            f"Hero generation failed for {product.id}/{ratio.ratio}: {exc}"
                        )
                        for _ in brief.languages:
                            progress.advance(task)
                            result.assets.append(GeneratedAsset(
                                product_id=product.id,
                                aspect_ratio=ratio.ratio,
                                language="*",
                                file_path="",
                                status=AssetStatus.FAILED,
                                hero_status=AssetStatus.FAILED,
                            ))
                            result.failed_count += 1
                        continue

                for lang in brief.languages:
                    progress.update(
                        task,
                        description=f"{product.id} / {ratio.ratio} / {lang}",
                    )

                    output_path = storage.creative_output_path(
                        brief.name, product.id, ratio.name, lang,
                    )

                    try:
                        # ── Layout rendering ──────────────────────────
                        _, rendered_texts = compositor.compose(
                            hero_path=hero_path,
                            output_path=output_path,
                            width=ratio.width,
                            height=ratio.height,
                            campaign_message=brief.message,
                            tagline=brief.tagline,
                            brand_name=brief.brand,
                            language=lang,
                            product_name=product.name,
                        )

                        # ── Stage 5: Policy checks ───────────────────
                        brand_result = brand_checker.full_check(
                            image_path=output_path,
                            rendered_texts=rendered_texts,
                            logo_was_placed=compositor.logo_placed,
                        )
                        legal_result = legal_checker.check(rendered_texts)

                        asset = GeneratedAsset(
                            product_id=product.id,
                            aspect_ratio=ratio.ratio,
                            language=lang,
                            file_path=str(output_path),
                            status=AssetStatus.GENERATED,
                            hero_status=hero_status,
                            prompt_used=hero_prompt,
                            brand_compliance=brand_result,
                            legal_compliance=legal_result,
                            rendered_texts=rendered_texts,
                        )
                        result.assets.append(asset)
                        result.generated_count += 1

                    except Exception as exc:
                        logger.error(f"Composition failed: {exc}", exc_info=True)
                        result.assets.append(GeneratedAsset(
                            product_id=product.id,
                            aspect_ratio=ratio.ratio,
                            language=lang,
                            file_path="",
                            status=AssetStatus.FAILED,
                            hero_status=hero_status,
                        ))
                        result.failed_count += 1
                        result.warnings.append(
                            f"Composition failed for {product.id}/{ratio.ratio}/{lang}: {exc}"
                        )

                    progress.advance(task)

    # ── Collect translation warnings ──────────────────────────────────
    for tw in translator.warnings:
        result.warnings.append(f"[Translation] {tw}")

    result.total_assets = len(result.assets)
    result.reused_count = sum(
        1 for a in result.assets if a.hero_status == AssetStatus.REUSED
    )
    result.elapsed_seconds = time.time() - start

    # ── Stage 6: Reporting ────────────────────────────────────────────
    campaign_dir = storage.get_campaign_dir(brief.name)
    print_console_report(result)
    save_json_report(result, campaign_dir)
    save_html_report(result, campaign_dir)

    console.print(
        f"[bold green]✓ Done![/bold green] "
        f"Outputs saved to: [cyan]{campaign_dir}[/cyan]\n"
    )
    return result
