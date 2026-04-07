"""Tests for the performance analytics module."""

from pathlib import Path

from src.analytics import (
    generate_sample_kpis,
    detect_winner,
    build_performance_report,
    export_kpis_csv,
    CreativeKPI,
)


SAMPLE_ASSETS = [
    {"product_id": "product-a", "aspect_ratio": "1:1", "language": "en"},
    {"product_id": "product-a", "aspect_ratio": "9:16", "language": "en"},
    {"product_id": "product-a", "aspect_ratio": "16:9", "language": "en"},
    {"product_id": "product-b", "aspect_ratio": "1:1", "language": "en"},
    {"product_id": "product-b", "aspect_ratio": "1:1", "language": "es"},
]


class TestGenerateSampleKPIs:
    def test_returns_one_kpi_per_asset(self):
        kpis = generate_sample_kpis(SAMPLE_ASSETS)
        assert len(kpis) == len(SAMPLE_ASSETS)

    def test_deterministic_with_seed(self):
        kpis1 = generate_sample_kpis(SAMPLE_ASSETS, seed=123)
        kpis2 = generate_sample_kpis(SAMPLE_ASSETS, seed=123)
        for k1, k2 in zip(kpis1, kpis2):
            assert k1.spend_usd == k2.spend_usd
            assert k1.impressions == k2.impressions

    def test_kpi_fields_positive(self):
        kpis = generate_sample_kpis(SAMPLE_ASSETS)
        for k in kpis:
            assert k.spend_usd > 0
            assert k.impressions > 0
            assert k.clicks > 0
            assert k.conversions >= 1

    def test_ctr_calculation(self):
        k = CreativeKPI(
            creative_id="test", product_id="p", aspect_ratio="1:1",
            language="en", spend_usd=100, impressions=1000, clicks=25, conversions=5,
        )
        assert k.ctr == 2.5

    def test_cpa_calculation(self):
        k = CreativeKPI(
            creative_id="test", product_id="p", aspect_ratio="1:1",
            language="en", spend_usd=100, impressions=1000, clicks=25, conversions=5,
        )
        assert k.cpa == 20.0

    def test_zero_impressions_ctr(self):
        k = CreativeKPI(
            creative_id="test", product_id="p", aspect_ratio="1:1",
            language="en", spend_usd=0, impressions=0, clicks=0, conversions=0,
        )
        assert k.ctr == 0.0


class TestDetectWinner:
    def test_winner_has_lowest_cpa(self):
        kpis = generate_sample_kpis(SAMPLE_ASSETS)
        winner = detect_winner(kpis)
        assert winner is not None
        eligible = [k for k in kpis if k.conversions >= 2]
        assert winner.cpa == min(k.cpa for k in eligible)

    def test_no_winner_with_no_conversions(self):
        kpis = [
            CreativeKPI(
                creative_id="a", product_id="p", aspect_ratio="1:1",
                language="en", spend_usd=100, impressions=1000, clicks=10, conversions=1,
            ),
        ]
        winner = detect_winner(kpis)
        assert winner is None  # needs >= 2 conversions


class TestBuildPerformanceReport:
    def test_aggregates_totals(self):
        report = build_performance_report(SAMPLE_ASSETS)
        assert report.total_spend > 0
        assert report.total_impressions > 0
        assert report.total_clicks > 0
        assert report.total_conversions > 0
        assert report.avg_ctr > 0
        assert report.avg_cpa > 0

    def test_winner_detected(self):
        report = build_performance_report(SAMPLE_ASSETS)
        assert report.winner is not None
        assert report.winner.creative_id in [k.creative_id for k in report.kpis]


class TestExportCSV:
    def test_csv_round_trip(self, tmp_path):
        kpis = generate_sample_kpis(SAMPLE_ASSETS)
        csv_path = export_kpis_csv(kpis, tmp_path / "kpis.csv")
        assert csv_path.exists()
        lines = csv_path.read_text().strip().split("\n")
        assert len(lines) == len(SAMPLE_ASSETS) + 1  # header + data rows
        header = lines[0]
        assert "creative_id" in header
        assert "ctr_pct" in header
        assert "cpa_usd" in header
