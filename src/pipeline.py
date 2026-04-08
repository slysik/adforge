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
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import yaml
from PIL import Image as PILImage
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from .models import (
    CampaignBrief, PipelineResult, GeneratedAsset, AssetStatus,
)
from .providers import get_provider, ImageProvider, GenerationMetadata
from .analyzer import analyze_brief
from .templates import LayoutTemplate, auto_select_template
from .compositor import Compositor, TranslationProvider, get_translator
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
# Pipeline helpers
# -----------------------------------------------------------------------

@dataclass
class PipelineServices:
    """Long-lived collaborators used across pipeline stages."""
    provider: ImageProvider
    storage: StorageManager
    compositor: Compositor
    brand_checker: BrandComplianceChecker
    legal_checker: LegalChecker
    translator: TranslationProvider
    forced_template: LayoutTemplate | None


@dataclass
class HeroArtifacts:
    """Per-product hero resolution and generation outputs."""
    existing_hero: Path | None
    hero_status: AssetStatus
    paths: dict[str, Path] = field(default_factory=dict)
    prompts: dict[str, str] = field(default_factory=dict)
    metas: dict[str, GenerationMetadata] = field(default_factory=dict)


def _build_reporter(
    status_callback: Optional[Callable[[str], None]],
) -> Callable[[str], None]:
    """Create a single reporting sink for CLI and optional callbacks."""
    def report(msg: str) -> None:
        if status_callback:
            status_callback(msg)
        console.print(f"[bold blue]Pipeline:[/bold blue] {msg}")

    return report


def _resolve_forced_template(template: str | None) -> LayoutTemplate | None:
    """Resolve a user-forced template name, falling back to auto-select."""
    if not template:
        return None

    try:
        return LayoutTemplate(template)
    except ValueError:
        console.print(f"[yellow]⚠ Unknown template '{template}', using auto-select[/yellow]")
        return None


def _initialize_services(
    brief: CampaignBrief,
    input_dir: str | Path,
    output_dir: str | Path,
    mock: bool,
    api_key: str | None,
    provider_type: str | None,
    template: str | None,
) -> PipelineServices:
    """Build shared service objects used throughout the run."""
    provider = get_provider(
        provider_type=provider_type,
        api_key=api_key,
        mock=mock,
    )
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
    translator = get_translator()
    translator.clear_warnings()

    return PipelineServices(
        provider=provider,
        storage=storage,
        compositor=compositor,
        brand_checker=brand_checker,
        legal_checker=LegalChecker(),
        translator=translator,
        forced_template=_resolve_forced_template(template),
    )


def _cached_generation_metadata() -> GenerationMetadata:
    """Synthetic metadata for a hero loaded from the on-disk cache."""
    return GenerationMetadata(
        provider="cached",
        model="cache",
        prompt_used="(cached)",
        generation_time_ms=0,
        estimated_cost_usd=0.0,
    )


def _resolve_existing_hero(
    brief: CampaignBrief,
    product,
    storage: StorageManager,
) -> tuple[Path | None, AssetStatus]:
    """Resolve and copy an existing hero when the brief points to one."""
    auto_discover = (
        product.hero_image is not None
        or "hero_image" not in (product.model_fields_set or set())
    )
    existing_hero = storage.find_existing_hero(
        product.id,
        product.hero_image,
        auto_discover=auto_discover,
    )
    if not existing_hero:
        return None, AssetStatus.GENERATED

    copied = storage.copy_hero_to_output(existing_hero, brief.name, product.id)
    return copied, AssetStatus.REUSED


def _build_product_prompt(
    brief: CampaignBrief,
    product,
    enrichments: dict[str, str],
) -> str:
    """Build the hero generation prompt for a single product."""
    return _build_prompt(
        product_name=product.name,
        product_description=product.description,
        keywords=product.keywords,
        campaign_message=brief.message,
        target_audience=brief.target_audience,
        target_region=brief.target_region,
        brand_name=brief.brand,
        enrichment=enrichments.get(product.id, ""),
    )


def _record_cached_hero(
    artifacts: HeroArtifacts,
    ratio,
    hero_out: Path,
    stage,
) -> None:
    """Record a cache hit for a ratio-specific hero image."""
    artifacts.paths[ratio.name] = hero_out
    artifacts.prompts[ratio.name] = "(cached)"
    artifacts.metas[ratio.name] = _cached_generation_metadata()
    stage.items_processed += 1
    console.print(f"  [dim]↳ Cached hero ({ratio.ratio}): {hero_out}[/dim]")


def _record_generated_hero(
    artifacts: HeroArtifacts,
    ratio,
    path: Path,
    meta: GenerationMetadata,
    stage,
) -> None:
    """Record a newly generated hero image and its metrics."""
    artifacts.paths[ratio.name] = path
    artifacts.prompts[ratio.name] = meta.prompt_used
    artifacts.metas[ratio.name] = meta
    stage.api_calls += 1
    stage.estimated_cost_usd += meta.estimated_cost_usd
    stage.items_processed += 1
    console.print(
        f"  [green]✓ Hero ({ratio.ratio}): {path} "
        f"[dim]({meta.generation_time_ms}ms)[/dim][/green]"
    )


def _record_hero_generation_failure(
    result: PipelineResult,
    product_id: str,
    ratio_label: str,
    exc: Exception,
) -> None:
    """Log and persist a hero generation warning without stopping the run."""
    console.print(f"  [red]✗ Hero gen failed ({ratio_label}): {exc}[/red]")
    result.warnings.append(
        f"Hero generation failed for {product_id}/{ratio_label}: {exc}"
    )


def _generate_product_heroes(
    brief: CampaignBrief,
    product,
    services: PipelineServices,
    tracker: PipelineTracker,
    result: PipelineResult,
    enrichments: dict[str, str],
    parallel: bool,
    max_workers: int,
    report: Callable[[str], None],
) -> HeroArtifacts:
    """Resolve reused heroes or generate the missing ratio-specific ones."""
    existing_hero, hero_status = _resolve_existing_hero(brief, product, services.storage)
    artifacts = HeroArtifacts(existing_hero=existing_hero, hero_status=hero_status)

    if existing_hero is not None:
        return artifacts

    report(f"Generating heroes for {product.name}...")
    prompt = _build_product_prompt(brief, product, enrichments)

    with tracker.stage(f"hero_gen_{product.id}") as stage:
        if parallel and len(brief.aspect_ratios) > 1:
            futures = {}
            with ThreadPoolExecutor(max_workers=max_workers) as pool:
                for ratio in brief.aspect_ratios:
                    hero_out = services.storage.hero_output_path(
                        brief.name, product.id, ratio.name,
                    )
                    if _check_cached_hero(hero_out):
                        _record_cached_hero(artifacts, ratio, hero_out, stage)
                        continue

                    future = pool.submit(
                        _generate_hero_task,
                        services.provider,
                        prompt,
                        ratio.width,
                        ratio.height,
                        hero_out,
                    )
                    futures[future] = ratio

                for future in as_completed(futures):
                    ratio = futures[future]
                    try:
                        path, meta = future.result()
                        _record_generated_hero(artifacts, ratio, path, meta, stage)
                    except Exception as exc:
                        _record_hero_generation_failure(result, product.id, ratio.ratio, exc)
        else:
            for ratio in brief.aspect_ratios:
                hero_out = services.storage.hero_output_path(
                    brief.name, product.id, ratio.name,
                )
                if _check_cached_hero(hero_out):
                    _record_cached_hero(artifacts, ratio, hero_out, stage)
                    continue

                try:
                    _, meta = services.provider.generate(
                        prompt=prompt,
                        width=ratio.width,
                        height=ratio.height,
                        output_path=hero_out,
                    )
                    _record_generated_hero(artifacts, ratio, hero_out, meta, stage)
                except Exception as exc:
                    _record_hero_generation_failure(result, product.id, ratio.ratio, exc)

    return artifacts


def _append_failed_asset(
    result: PipelineResult,
    product_id: str,
    aspect_ratio: str,
    language: str,
    hero_status: AssetStatus,
) -> None:
    """Append a failed asset placeholder to preserve output accounting."""
    result.assets.append(GeneratedAsset(
        product_id=product_id,
        aspect_ratio=aspect_ratio,
        language=language,
        file_path="",
        status=AssetStatus.FAILED,
        hero_status=hero_status,
    ))
    result.failed_count += 1


def _track_asset_metrics(
    tracker: PipelineTracker,
    product_id: str,
    aspect_ratio: str,
    language: str,
    meta: GenerationMetadata | None,
    composition_ms: int,
    validation_ms: int,
) -> None:
    """Capture per-asset timing and provider usage."""
    tracker.track_asset(AssetMetrics(
        product_id=product_id,
        aspect_ratio=aspect_ratio,
        language=language,
        provider=meta.provider if meta else "reused",
        generation_ms=meta.generation_time_ms if meta else 0,
        composition_ms=composition_ms,
        validation_ms=validation_ms,
        estimated_cost_usd=meta.estimated_cost_usd if meta else 0.0,
    ))


def _compose_product_assets(
    brief: CampaignBrief,
    product,
    artifacts: HeroArtifacts,
    services: PipelineServices,
    tracker: PipelineTracker,
    result: PipelineResult,
    progress: Progress,
    task_id: int,
    report: Callable[[str], None],
) -> None:
    """Compose and validate every language/ratio creative for one product."""
    report("Compositing and Validating...")
    with tracker.stage(f"compose_{product.id}") as comp_stage, \
         tracker.stage(f"validate_{product.id}") as val_stage:
        for ratio in brief.aspect_ratios:
            hero_path = artifacts.paths.get(ratio.name) or artifacts.existing_hero

            if hero_path is None:
                for lang in brief.languages:
                    progress.advance(task_id)
                    _append_failed_asset(
                        result,
                        product.id,
                        ratio.ratio,
                        lang,
                        AssetStatus.FAILED,
                    )
                continue

            for lang in brief.languages:
                progress.update(
                    task_id,
                    description=f"{product.id} / {ratio.ratio} / {lang}",
                )
                output_path = services.storage.creative_output_path(
                    brief.name, product.id, ratio.name, lang,
                )
                comp_start = time.time()

                try:
                    selected_template = services.forced_template or auto_select_template(
                        ratio.ratio,
                        product.keywords,
                        brief.message,
                    )
                    _, rendered_texts = services.compositor.compose(
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

                    val_start = time.time()
                    brand_result = services.brand_checker.full_check(
                        image_path=output_path,
                        rendered_texts=rendered_texts,
                        logo_was_placed=services.compositor.logo_placed,
                    )
                    legal_result = services.legal_checker.check(rendered_texts)
                    val_ms = int((time.time() - val_start) * 1000)
                    val_stage.items_processed += 1

                    result.assets.append(GeneratedAsset(
                        product_id=product.id,
                        aspect_ratio=ratio.ratio,
                        language=lang,
                        file_path=str(output_path),
                        status=AssetStatus.GENERATED,
                        hero_status=artifacts.hero_status,
                        prompt_used=artifacts.prompts.get(ratio.name),
                        brand_compliance=brand_result,
                        legal_compliance=legal_result,
                        rendered_texts=rendered_texts,
                    ))
                    result.created_count += 1
                    _track_asset_metrics(
                        tracker,
                        product.id,
                        ratio.ratio,
                        lang,
                        artifacts.metas.get(ratio.name),
                        comp_ms,
                        val_ms,
                    )
                except Exception as exc:
                    logger.error(f"Composition failed: {exc}", exc_info=True)
                    _append_failed_asset(
                        result,
                        product.id,
                        ratio.ratio,
                        lang,
                        artifacts.hero_status,
                    )
                    result.warnings.append(
                        f"Composition failed for {product.id}/{ratio.ratio}/{lang}: {exc}"
                    )

                progress.advance(task_id)


def _finalize_result(
    result: PipelineResult,
    translator: TranslationProvider,
    start: float,
) -> None:
    """Populate final aggregate counters after asset processing."""
    for warning in translator.warnings:
        result.warnings.append(f"[Translation] {warning}")

    result.total_assets = len(result.assets)
    result.hero_reused_count = sum(
        1 for asset in result.assets if asset.hero_status == AssetStatus.REUSED
    )
    result.elapsed_seconds = time.time() - start


def _write_reports(
    brief: CampaignBrief,
    result: PipelineResult,
    services: PipelineServices,
    metrics,
    analysis,
    report: Callable[[str], None],
) -> None:
    """Print, serialize, and package final pipeline outputs."""
    report("Generating Reports...")
    campaign_dir = services.storage.get_campaign_dir(brief.name)
    print_console_report(result)
    print_metrics(metrics)

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

    report("Packaging ZIP...")
    services.storage.package_campaign_zip(brief.name)
    console.print(
        f"[bold green]✓ Done![/bold green] "
        f"Outputs saved to: [cyan]{campaign_dir}[/cyan]\n"
    )


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
    status_callback: Callable[[str], None] | None = None,
) -> PipelineResult:
    """Execute the full creative automation pipeline."""
    report = _build_reporter(status_callback)
    tracker = PipelineTracker()
    start = time.time()

    report("Ingesting Brief...")
    with tracker.stage("brief_ingestion") as stage:
        brief = load_brief(brief_path)
        stage.items_processed = 1
        stage.notes.append(f"Loaded: {brief.name}")

    analysis = None
    enrichments: dict[str, str] = {}
    if analyze:
        report("Analyzing Brief...")
        with tracker.stage("brief_analysis") as stage:
            analysis = analyze_brief(brief)
            enrichments = analysis.prompt_enrichments
            stage.items_processed = 1
            stage.notes.append(f"Score: {analysis.score.overall}/100")

    report("Initializing...")
    services = _initialize_services(
        brief,
        input_dir,
        output_dir,
        mock,
        api_key,
        provider_type,
        template,
    )

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
        task_id = progress.add_task("Generating creatives…", total=total_tasks)

        for product in brief.products:
            console.print(f"\n[bold white]▸ Product: {product.name}[/bold white]")
            report(f"Resolving assets for {product.name}...")
            artifacts = _generate_product_heroes(
                brief,
                product,
                services,
                tracker,
                result,
                enrichments,
                parallel,
                max_workers,
                report,
            )
            _compose_product_assets(
                brief,
                product,
                artifacts,
                services,
                tracker,
                result,
                progress,
                task_id,
                report,
            )

    _finalize_result(result, services.translator, start)
    metrics = tracker.finalize()
    metrics.provider_used = (
        f"{services.provider.provider_type.value} ({services.provider.model_name})"
    )
    _write_reports(brief, result, services, metrics, analysis, report)
    return result
