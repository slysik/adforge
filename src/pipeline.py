"""
Main creative automation pipeline orchestrator.

Stages:
  1. Brief ingestion — parse, validate, log
  2. Brief analysis — score quality, suggest improvements, enrich prompts
  3. Asset resolution — discover existing heroes or mark for generation
  4. Hero generation — generate missing heroes via GenAI (parallel, per-ratio)
  5. Layout rendering — compose creatives using auto-selected templates
  6. Policy checks — brand compliance + legal checks against rendered output
  7. Reporting — console summary, JSON, HTML dashboard, metrics

Provider chain: Adobe Firefly → DALL-E 3 → Mock (auto-resolved)
"""

from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Optional

import yaml
from PIL import Image as PILImage
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .models import (
    CampaignBrief, PipelineResult, GeneratedAsset,
    AssetStatus, ComplianceStatus, ComplianceResult,
)
from .providers import get_provider, ImageProvider, GenerationMetadata
from .analyzer import analyze_brief, print_analysis
from .templates import LayoutTemplate, auto_select_template, TEMPLATE_RENDERERS
from .compositor import Compositor, get_translator, _hex_to_rgb
from .validator import BrandComplianceChecker, LegalChecker
from .storage import StorageManager
from .tracker import PipelineTracker, AssetMetrics, print_metrics
from .report import print_console_report, save_json_report, save_html_report

console = Console()
logger = logging.getLogger("adforge")


# -----------------------------------------------------------------------
# Hero caching utility
# -----------------------------------------------------------------------

def _check_cached_hero(hero_out: Path) -> bool:
    """Check if a cached hero image exists and is valid.

    Validates that the file exists and can be opened as a valid image.
    If the cache file is corrupt, returns False to trigger regeneration.
    """
    if not hero_out.exists():
        return False

    try:
        with PILImage.open(str(hero_out)) as img:
            img.verify()
        return True
    except Exception:
        # Corrupt or invalid cache file
        return False


# -----------------------------------------------------------------------
# Prompt builder
# -----------------------------------------------------------------------

def _build_prompt(
    product_name: str,
    product_description: str,
    keywords: list[str],
    campaign_message: str,
    target_audience: str,
    target_region: str,
    brand_name: str,
    enrichment: str = "",
) -> str:
    """Build a rich generation prompt with optional enrichment from brief analysis."""
    kw = ", ".join(keywords) if keywords else ""
    base = (
        f"A high-quality, professional advertising photograph for a social media campaign. "
        f"Product: {product_name} – {product_description}. "
        f"Brand: {brand_name}. "
        f"Campaign theme: {campaign_message}. "
        f"Target audience: {target_audience} in {target_region}. "
        f"Visual keywords: {kw}. "
        f"The image should be vibrant, eye-catching, product-centric, clean background, "
        f"studio lighting, modern and aspirational lifestyle feel. "
        f"Do NOT include any text, watermarks, logos, or words in the image."
    )
    if enrichment:
        base += f" Creative direction: {enrichment}"
    return base


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

    if "campaign" in data:
        data = data["campaign"]

    return CampaignBrief(**data)


# -----------------------------------------------------------------------
# Stage 3: Parallel hero generation
# -----------------------------------------------------------------------

def _generate_hero_task(
    provider: ImageProvider,
    prompt: str,
    width: int,
    height: int,
    output_path: Path,
) -> tuple[Path, GenerationMetadata]:
    """Generate a single hero image (designed for thread pool execution)."""
    _, meta = provider.generate(
        prompt=prompt,
        width=width,
        height=height,
        output_path=output_path,
    )
    return output_path, meta


# -----------------------------------------------------------------------
# Main pipeline
# -----------------------------------------------------------------------

def run_pipeline(
    brief_path: str | Path,
    input_dir: str | Path = "input_assets",
    output_dir: str | Path = "output",
    mock: bool = False,
    api_key: str | None = None,
    provider_type: str | None = None,
    template: str | None = None,
    analyze: bool = True,
    parallel: bool = True,
    max_workers: int = 4,
) -> PipelineResult:
    """Execute the full creative automation pipeline.

    Args:
        brief_path: Path to YAML/JSON campaign brief
        input_dir: Directory with existing assets
        output_dir: Output directory for generated creatives
        mock: Force mock image generation
        api_key: API key for image provider
        provider_type: Force a specific provider ("firefly", "dalle", "mock")
        template: Force a specific layout template name
        analyze: Run brief analysis (default True)
        parallel: Parallelize hero generation (default True)
        max_workers: Thread pool size for parallel generation
    """
    tracker = PipelineTracker()
    start = time.time()

    # ── Stage 1: Brief normalization ──────────────────────────────────
    console.print("\n[bold cyan]━━━ AdForge ━━━[/bold cyan]\n")

    with tracker.stage("brief_ingestion") as stage:
        brief = load_brief(brief_path)
        stage.items_processed = 1
        stage.notes.append(f"Loaded: {brief.name}")

    console.print(f"[bold]Campaign:[/bold] {brief.name}")
    console.print(f"[bold]Brand:[/bold]    {brief.brand}")
    console.print(f"[bold]Region:[/bold]   {brief.target_region}")
    console.print(f"[bold]Audience:[/bold] {brief.target_audience}")
    console.print(f"[bold]Products:[/bold] {len(brief.products)}")
    console.print(f"[bold]Ratios:[/bold]   {', '.join(r.ratio for r in brief.aspect_ratios)}")
    console.print(f"[bold]Languages:[/bold] {', '.join(brief.languages)}")
    if brief.brand_guidelines.required_disclaimer:
        console.print(f"[bold]Disclaimer:[/bold] {brief.brand_guidelines.required_disclaimer}")

    # ── Stage 2: Brief analysis ───────────────────────────────────────
    analysis = None
    enrichments = {}
    if analyze:
        with tracker.stage("brief_analysis") as stage:
            analysis = analyze_brief(brief)
            enrichments = analysis.prompt_enrichments
            stage.items_processed = 1
            stage.notes.append(f"Score: {analysis.score.overall}/100")

        print_analysis(analysis)

    # ── Initialize components ─────────────────────────────────────────
    provider = get_provider(
        provider_type=provider_type,
        api_key=api_key,
        mock=mock,
    )
    console.print(f"[bold]Provider:[/bold] {provider.provider_type.value} ({provider.model_name})")
    console.print()

    storage = StorageManager(input_dir=Path(input_dir), output_dir=Path(output_dir))
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

    # Resolve template
    forced_template = None
    if template:
        try:
            forced_template = LayoutTemplate(template)
        except ValueError:
            console.print(f"[yellow]⚠ Unknown template '{template}', using auto-select[/yellow]")

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

            # ── Stage 3: Asset resolution ─────────────────────────────
            # When hero_image is explicitly null, skip auto-discovery to force generation
            auto_discover = product.hero_image is not None or "hero_image" not in (product.model_fields_set or set())
            existing_hero = storage.find_existing_hero(product.id, product.hero_image, auto_discover=auto_discover)
            hero_status = AssetStatus.REUSED if existing_hero else AssetStatus.GENERATED

            if existing_hero:
                existing_hero = storage.copy_hero_to_output(
                    existing_hero, brief.name, product.id,
                )

            if existing_hero is None:
                console.print(f"  [yellow]↳ No existing hero – will generate per ratio[/yellow]")

            # ── Stage 4: Hero generation (parallel when possible) ─────
            hero_paths: dict[str, Path] = {}  # ratio_name → hero_path
            hero_prompts: dict[str, str] = {}
            hero_metas: dict[str, GenerationMetadata] = {}

            if existing_hero is None:
                prompt_enrichment = enrichments.get(product.id, "")
                gen_prompt = _build_prompt(
                    product_name=product.name,
                    product_description=product.description,
                    keywords=product.keywords,
                    campaign_message=brief.message,
                    target_audience=brief.target_audience,
                    target_region=brief.target_region,
                    brand_name=brief.brand,
                    enrichment=prompt_enrichment,
                )

                with tracker.stage(f"hero_gen_{product.id}") as stage:
                    if parallel and len(brief.aspect_ratios) > 1:
                        # Parallel hero generation across ratios
                        # With hero caching: check for existing valid images before submitting tasks
                        futures = {}
                        with ThreadPoolExecutor(max_workers=max_workers) as pool:
                            for ratio in brief.aspect_ratios:
                                hero_out = storage.hero_output_path(
                                    brief.name, product.id, ratio.name,
                                )

                                # Check if cached hero exists and is valid
                                if _check_cached_hero(hero_out):
                                    hero_paths[ratio.name] = hero_out
                                    hero_prompts[ratio.name] = "(cached)"
                                    # Create a cached metadata entry with zero cost/time
                                    hero_metas[ratio.name] = GenerationMetadata(
                                        provider="cached",
                                        model_name="cache",
                                        prompt_used="(cached)",
                                        generation_time_ms=0,
                                        estimated_cost_usd=0.0,
                                    )
                                    stage.items_processed += 1
                                    console.print(
                                        f"  [dim]↳ Cached hero ({ratio.ratio}): {hero_out}[/dim]"
                                    )
                                    continue

                                f = pool.submit(
                                    _generate_hero_task,
                                    provider, gen_prompt,
                                    ratio.width, ratio.height, hero_out,
                                )
                                futures[f] = ratio

                            for f in as_completed(futures):
                                ratio = futures[f]
                                try:
                                    path, meta = f.result()
                                    hero_paths[ratio.name] = path
                                    hero_prompts[ratio.name] = meta.prompt_used
                                    hero_metas[ratio.name] = meta
                                    stage.api_calls += 1
                                    stage.estimated_cost_usd += meta.estimated_cost_usd
                                    stage.items_processed += 1
                                    console.print(
                                        f"  [green]✓ Hero ({ratio.ratio}): {path} "
                                        f"[dim]({meta.generation_time_ms}ms)[/dim][/green]"
                                    )
                                except Exception as exc:
                                    console.print(f"  [red]✗ Hero gen failed ({ratio.ratio}): {exc}[/red]")
                                    result.warnings.append(
                                        f"Hero generation failed for {product.id}/{ratio.ratio}: {exc}"
                                    )
                    else:
                        # Sequential fallback
                        # With hero caching: check for existing valid images before generating
                        for ratio in brief.aspect_ratios:
                            hero_out = storage.hero_output_path(
                                brief.name, product.id, ratio.name,
                            )

                            # Check if cached hero exists and is valid
                            if _check_cached_hero(hero_out):
                                hero_paths[ratio.name] = hero_out
                                hero_prompts[ratio.name] = "(cached)"
                                # Create a cached metadata entry with zero cost/time
                                hero_metas[ratio.name] = GenerationMetadata(
                                    provider="cached",
                                    model_name="cache",
                                    prompt_used="(cached)",
                                    generation_time_ms=0,
                                    estimated_cost_usd=0.0,
                                )
                                stage.items_processed += 1
                                console.print(
                                    f"  [dim]↳ Cached hero ({ratio.ratio}): {hero_out}[/dim]"
                                )
                                continue

                            try:
                                _, meta = provider.generate(
                                    prompt=gen_prompt,
                                    width=ratio.width,
                                    height=ratio.height,
                                    output_path=hero_out,
                                )
                                hero_paths[ratio.name] = hero_out
                                hero_prompts[ratio.name] = meta.prompt_used
                                hero_metas[ratio.name] = meta
                                stage.api_calls += 1
                                stage.estimated_cost_usd += meta.estimated_cost_usd
                                stage.items_processed += 1
                                console.print(
                                    f"  [green]✓ Hero ({ratio.ratio}): {hero_out} "
                                    f"[dim]({meta.generation_time_ms}ms)[/dim][/green]"
                                )
                            except Exception as exc:
                                console.print(f"  [red]✗ Hero gen failed ({ratio.ratio}): {exc}[/red]")
                                result.warnings.append(
                                    f"Hero generation failed for {product.id}/{ratio.ratio}: {exc}"
                                )

            # ── Stage 5+6: Composition + validation per language ──────
            with tracker.stage(f"compose_{product.id}") as comp_stage, \
                 tracker.stage(f"validate_{product.id}") as val_stage:
                for ratio in brief.aspect_ratios:
                    hero_path = hero_paths.get(ratio.name) or existing_hero

                    if hero_path is None:
                        for lang in brief.languages:
                            progress.advance(task)
                            result.assets.append(GeneratedAsset(
                                product_id=product.id,
                                aspect_ratio=ratio.ratio,
                                language=lang,
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

                        comp_start = time.time()

                        try:
                            # Select layout template
                            selected_template = forced_template or auto_select_template(
                                ratio.ratio, product.keywords, brief.message,
                            )

                            # ── Layout rendering with template ────────────
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
                                template=selected_template,
                            )

                            comp_ms = int((time.time() - comp_start) * 1000)
                            comp_stage.items_processed += 1

                            # ── Policy checks ─────────────────────────────
                            val_start = time.time()
                            brand_result = brand_checker.full_check(
                                image_path=output_path,
                                rendered_texts=rendered_texts,
                                logo_was_placed=compositor.logo_placed,
                            )
                            legal_result = legal_checker.check(rendered_texts)
                            val_ms = int((time.time() - val_start) * 1000)
                            val_stage.items_processed += 1

                            # Prompt used for this hero
                            hero_prompt = hero_prompts.get(ratio.name)

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
                            result.created_count += 1

                            # Track per-asset metrics
                            gen_meta = hero_metas.get(ratio.name)
                            tracker.track_asset(AssetMetrics(
                                product_id=product.id,
                                aspect_ratio=ratio.ratio,
                                language=lang,
                                provider=gen_meta.provider if gen_meta else "reused",
                                generation_ms=gen_meta.generation_time_ms if gen_meta else 0,
                                composition_ms=comp_ms,
                                validation_ms=val_ms,
                                estimated_cost_usd=gen_meta.estimated_cost_usd if gen_meta else 0.0,
                            ))

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
    result.hero_reused_count = sum(
        1 for a in result.assets if a.hero_status == AssetStatus.REUSED
    )
    result.elapsed_seconds = time.time() - start

    # ── Finalize metrics ──────────────────────────────────────────────
    metrics = tracker.finalize()
    metrics.provider_used = f"{provider.provider_type.value} ({provider.model_name})"

    # ── Stage 7: Reporting ────────────────────────────────────────────
    campaign_dir = storage.get_campaign_dir(brief.name)
    print_console_report(result)
    print_metrics(metrics)

    # Estimate time saved vs manual workflow
    # Industry benchmark: ~15 min per creative manually (design + resize + text + review)
    manual_minutes_per_creative = 15
    manual_total_minutes = result.created_count * manual_minutes_per_creative
    automated_minutes = result.elapsed_seconds / 60
    time_saved_minutes = max(0, manual_total_minutes - automated_minutes)
    time_saved_hours = time_saved_minutes / 60

    console.print(
        f"  [bold]⏱ Estimated time saved:[/bold] "
        f"[green]{time_saved_hours:.1f} hours[/green] "
        f"({result.created_count} creatives × {manual_minutes_per_creative} min manual "
        f"= {manual_total_minutes} min vs {result.elapsed_seconds:.1f}s automated)"
    )
    console.print()

    save_json_report(
        result, campaign_dir,
        metrics=metrics, analysis=analysis,
        time_saved_minutes=time_saved_minutes,
    )
    save_html_report(
        result, campaign_dir,
        metrics=metrics, analysis=analysis,
        time_saved_minutes=time_saved_minutes,
    )

    # ── Package campaign as ZIP for delivery ──────────────────────────
    zip_path = storage.package_campaign_zip(brief.name)

    console.print(
        f"[bold green]✓ Done![/bold green] "
        f"Outputs saved to: [cyan]{campaign_dir}[/cyan]\n"
    )
    return result
