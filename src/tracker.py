"""
Pipeline performance and cost tracker.

Tracks per-stage timing and estimated costs for the full pipeline run.
This is essential for client-facing work — creative automation at scale
needs cost visibility per campaign, per asset, and per API call.

In production, this would integrate with:
  - Adobe Admin Console for Firefly credit tracking
  - Cloud cost management (AWS Cost Explorer, Azure Cost Analysis)
  - Client billing systems for usage-based pricing
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.table import Table

console = Console()


@dataclass
class StageMetrics:
    """Timing and cost for a single pipeline stage."""
    name: str
    started: float = 0.0
    elapsed_ms: int = 0
    items_processed: int = 0
    api_calls: int = 0
    estimated_cost_usd: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class AssetMetrics:
    """Per-asset generation metrics."""
    product_id: str
    aspect_ratio: str
    language: str
    provider: str = ""
    generation_ms: int = 0
    composition_ms: int = 0
    validation_ms: int = 0
    estimated_cost_usd: float = 0.0


@dataclass
class PipelineMetrics:
    """Aggregate pipeline performance and cost metrics."""
    stages: list[StageMetrics] = field(default_factory=list)
    assets: list[AssetMetrics] = field(default_factory=list)
    total_elapsed_ms: int = 0
    total_api_calls: int = 0
    total_estimated_cost_usd: float = 0.0
    provider_used: str = ""

    def to_dict(self) -> dict:
        """Serialize to dict for JSON reporting."""
        return {
            "total_elapsed_ms": self.total_elapsed_ms,
            "total_api_calls": self.total_api_calls,
            "total_estimated_cost_usd": round(self.total_estimated_cost_usd, 4),
            "provider": self.provider_used,
            "stages": [
                {
                    "name": s.name,
                    "elapsed_ms": s.elapsed_ms,
                    "items_processed": s.items_processed,
                    "api_calls": s.api_calls,
                    "estimated_cost_usd": round(s.estimated_cost_usd, 4),
                    "notes": s.notes,
                }
                for s in self.stages
            ],
            "per_asset": [
                {
                    "product_id": a.product_id,
                    "aspect_ratio": a.aspect_ratio,
                    "language": a.language,
                    "provider": a.provider,
                    "generation_ms": a.generation_ms,
                    "composition_ms": a.composition_ms,
                    "validation_ms": a.validation_ms,
                    "estimated_cost_usd": round(a.estimated_cost_usd, 4),
                }
                for a in self.assets
            ],
        }


class PipelineTracker:
    """Tracks performance and cost across pipeline stages.

    Usage:
        tracker = PipelineTracker()
        with tracker.stage("hero_generation") as stage:
            # do work
            stage.api_calls += 1
            stage.estimated_cost_usd += 0.04

        metrics = tracker.finalize()
    """

    def __init__(self):
        self._start = time.time()
        self._stages: list[StageMetrics] = []
        self._assets: list[AssetMetrics] = []
        self._current_stage: Optional[StageMetrics] = None

    class _StageContext:
        """Context manager for tracking a pipeline stage."""
        def __init__(self, stage: StageMetrics):
            self.stage = stage

        def __enter__(self) -> StageMetrics:
            self.stage.started = time.time()
            return self.stage

        def __exit__(self, *args):
            self.stage.elapsed_ms = int((time.time() - self.stage.started) * 1000)

    def stage(self, name: str) -> _StageContext:
        """Start tracking a new pipeline stage."""
        s = StageMetrics(name=name)
        self._stages.append(s)
        self._current_stage = s
        return self._StageContext(s)

    def track_asset(self, asset: AssetMetrics):
        """Record metrics for a single asset."""
        self._assets.append(asset)

    def finalize(self) -> PipelineMetrics:
        """Compute aggregate metrics."""
        total_ms = int((time.time() - self._start) * 1000)
        total_api = sum(s.api_calls for s in self._stages)
        total_cost = sum(s.estimated_cost_usd for s in self._stages)

        return PipelineMetrics(
            stages=self._stages,
            assets=self._assets,
            total_elapsed_ms=total_ms,
            total_api_calls=total_api,
            total_estimated_cost_usd=total_cost,
        )


def print_metrics(metrics: PipelineMetrics) -> None:
    """Print a performance summary table."""
    table = Table(title="Pipeline Performance", show_header=True, header_style="bold magenta")
    table.add_column("Stage", style="white")
    table.add_column("Time", justify="right", style="cyan")
    table.add_column("Items", justify="right")
    table.add_column("API Calls", justify="right")
    table.add_column("Est. Cost", justify="right", style="yellow")

    for s in metrics.stages:
        time_str = f"{s.elapsed_ms}ms" if s.elapsed_ms < 1000 else f"{s.elapsed_ms / 1000:.1f}s"
        cost_str = f"${s.estimated_cost_usd:.3f}" if s.estimated_cost_usd > 0 else "–"
        table.add_row(
            s.name, time_str, str(s.items_processed),
            str(s.api_calls), cost_str,
        )

    # Totals row
    total_time = f"{metrics.total_elapsed_ms}ms" if metrics.total_elapsed_ms < 1000 else f"{metrics.total_elapsed_ms / 1000:.1f}s"
    total_cost = f"${metrics.total_estimated_cost_usd:.3f}" if metrics.total_estimated_cost_usd > 0 else "$0.000"
    table.add_row(
        "[bold]TOTAL[/bold]", f"[bold]{total_time}[/bold]", "",
        f"[bold]{metrics.total_api_calls}[/bold]", f"[bold]{total_cost}[/bold]",
        style="bold",
    )

    console.print()
    console.print(table)
    console.print(f"  Provider: [cyan]{metrics.provider_used}[/cyan]")
    console.print()
