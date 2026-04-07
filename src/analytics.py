"""
Performance analytics for creative campaigns.

Generates sample KPI data and identifies winning creatives based on
spend efficiency (CTR, CPA). In production, this would ingest real
ad platform data; here we generate realistic demo data.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class CreativeKPI:
    """Performance metrics for a single creative asset."""
    creative_id: str
    product_id: str
    aspect_ratio: str
    language: str
    spend_usd: float
    impressions: int
    clicks: int
    conversions: int

    @property
    def ctr(self) -> float:
        """Click-through rate as a percentage."""
        return (self.clicks / self.impressions * 100) if self.impressions else 0.0

    @property
    def cpa(self) -> float:
        """Cost per acquisition."""
        return (self.spend_usd / self.conversions) if self.conversions else float("inf")

    @property
    def cpc(self) -> float:
        """Cost per click."""
        return (self.spend_usd / self.clicks) if self.clicks else float("inf")


@dataclass
class PerformanceReport:
    """Aggregated performance report with winner detection."""
    kpis: list[CreativeKPI] = field(default_factory=list)
    winner: CreativeKPI | None = None
    total_spend: float = 0.0
    total_impressions: int = 0
    total_clicks: int = 0
    total_conversions: int = 0
    avg_ctr: float = 0.0
    avg_cpa: float = 0.0


def generate_sample_kpis(
    assets: list[dict],
    seed: int = 42,
) -> list[CreativeKPI]:
    """Generate realistic sample KPI data for a set of creative assets.

    Uses seeded random to produce consistent demo data across runs.
    """
    rng = random.Random(seed)
    kpis = []

    for i, asset in enumerate(assets):
        product_id = asset.get("product_id", f"product_{i}")
        ratio = asset.get("aspect_ratio", "1:1")
        lang = asset.get("language", "en")

        # Simulate varying performance by ratio and language
        # 9:16 (stories) tends to get higher engagement
        ratio_boost = 1.3 if "9:16" in ratio else 1.0 if "1:1" in ratio else 0.9
        lang_boost = 1.0 if lang == "en" else 0.85

        spend = round(rng.uniform(50, 500) * ratio_boost, 2)
        impressions = int(rng.uniform(5000, 50000) * ratio_boost * lang_boost)
        base_ctr = rng.uniform(0.8, 4.5) * ratio_boost * lang_boost
        clicks = int(impressions * base_ctr / 100)
        conversion_rate = rng.uniform(1.5, 8.0) / 100
        conversions = max(1, int(clicks * conversion_rate))

        creative_id = f"{product_id}_{ratio.replace(':', 'x')}_{lang}"

        kpis.append(CreativeKPI(
            creative_id=creative_id,
            product_id=product_id,
            aspect_ratio=ratio,
            language=lang,
            spend_usd=spend,
            impressions=impressions,
            clicks=clicks,
            conversions=conversions,
        ))

    return kpis


def detect_winner(kpis: list[CreativeKPI]) -> CreativeKPI | None:
    """Identify the winning creative by lowest CPA (with minimum conversions)."""
    eligible = [k for k in kpis if k.conversions >= 2]
    if not eligible:
        return None
    return min(eligible, key=lambda k: k.cpa)


def build_performance_report(assets: list[dict], seed: int = 42) -> PerformanceReport:
    """Build a full performance report with winner detection."""
    kpis = generate_sample_kpis(assets, seed=seed)
    winner = detect_winner(kpis)

    report = PerformanceReport(
        kpis=kpis,
        winner=winner,
        total_spend=sum(k.spend_usd for k in kpis),
        total_impressions=sum(k.impressions for k in kpis),
        total_clicks=sum(k.clicks for k in kpis),
        total_conversions=sum(k.conversions for k in kpis),
    )
    if report.total_impressions:
        report.avg_ctr = report.total_clicks / report.total_impressions * 100
    if report.total_conversions:
        report.avg_cpa = report.total_spend / report.total_conversions

    return report


def export_kpis_csv(kpis: list[CreativeKPI], path: Path) -> Path:
    """Export KPI data to CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "creative_id", "product_id", "aspect_ratio", "language",
            "spend_usd", "impressions", "clicks", "conversions",
            "ctr_pct", "cpa_usd", "cpc_usd",
        ])
        for k in kpis:
            writer.writerow([
                k.creative_id, k.product_id, k.aspect_ratio, k.language,
                f"{k.spend_usd:.2f}", k.impressions, k.clicks, k.conversions,
                f"{k.ctr:.2f}", f"{k.cpa:.2f}" if k.cpa != float("inf") else "N/A",
                f"{k.cpc:.2f}" if k.cpc != float("inf") else "N/A",
            ])
    return path
