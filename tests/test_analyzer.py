"""Tests for the LLM-powered brief analyzer."""

import pytest

from src.models import (
    CampaignBrief, Product, AspectRatio, BrandGuidelines,
)
from src.analyzer import HeuristicAnalyzer, analyze_brief, BriefAnalysis


def _make_brief(**overrides):
    """Create a full brief for analysis testing."""
    defaults = dict(
        name="Summer Refresh 2025",
        brand="FreshCo",
        message="Stay Fresh This Summer",
        tagline="Naturally Refreshing",
        target_region="North America",
        target_audience="Health-conscious millennials and Gen Z, ages 22-38",
        languages=["en", "es"],
        brand_guidelines=BrandGuidelines(
            primary_colors=["#00A86B", "#FFFFFF", "#1B1B1B"],
            accent_color="#FFD700",
            font_family="Helvetica",
            logo_path="input_assets/logo.png",
            prohibited_words=["cheap", "discount"],
        ),
        products=[
            Product(
                id="sparkling-water",
                name="FreshCo Sparkling Water",
                description="Premium sparkling water with natural citrus essence, zero calories",
                keywords=["sparkling water", "citrus", "refreshing", "summer drink"],
            ),
            Product(
                id="green-smoothie",
                name="FreshCo Green Smoothie",
                description="Organic green smoothie blend with kale and ginger",
                hero_image="input_assets/green_smoothie.jpg",
                keywords=["green smoothie", "organic", "healthy"],
            ),
        ],
    )
    defaults.update(overrides)
    return CampaignBrief(**defaults)


class TestHeuristicAnalyzer:
    def test_returns_structured_analysis(self):
        brief = _make_brief()
        analysis = HeuristicAnalyzer().analyze(brief)
        assert isinstance(analysis, BriefAnalysis)
        assert analysis.score.overall > 0
        assert analysis.score.overall <= 100
        assert analysis.analyzed_by == "heuristic"

    def test_score_components_sum_to_overall(self):
        brief = _make_brief()
        analysis = HeuristicAnalyzer().analyze(brief)
        s = analysis.score
        assert s.overall == s.completeness + s.clarity + s.brand_strength + s.targeting

    def test_good_brief_scores_high(self):
        """A well-formed brief should score >= 60."""
        brief = _make_brief()
        analysis = HeuristicAnalyzer().analyze(brief)
        assert analysis.score.overall >= 60

    def test_identifies_strengths(self):
        brief = _make_brief()
        analysis = HeuristicAnalyzer().analyze(brief)
        assert len(analysis.strengths) > 0
        # Should recognize multi-language, brand palette, etc.
        assert any("Multi-language" in s for s in analysis.strengths)

    def test_identifies_missing_tagline(self):
        brief = _make_brief(tagline=None)
        analysis = HeuristicAnalyzer().analyze(brief)
        assert any("tagline" in s.lower() for s in analysis.suggestions)

    def test_identifies_weak_description(self):
        brief = _make_brief(products=[
            Product(id="prod-a", name="A", description="Short desc"),
            Product(id="prod-b", name="B", description="Also short"),
        ])
        analysis = HeuristicAnalyzer().analyze(brief)
        assert any("thin" in w.lower() or "description" in w.lower() for w in analysis.weaknesses)

    def test_identifies_missing_logo(self):
        brief = _make_brief(
            brand_guidelines=BrandGuidelines(primary_colors=["#000000", "#FFFFFF"]),
        )
        analysis = HeuristicAnalyzer().analyze(brief)
        assert any("logo" in w.lower() for w in analysis.weaknesses)

    def test_identifies_missing_disclaimer(self):
        brief = _make_brief()
        analysis = HeuristicAnalyzer().analyze(brief)
        assert any("disclaimer" in r.lower() for r in analysis.risk_flags)

    def test_generates_prompt_enrichments(self):
        """Products without hero_image should get prompt enrichments."""
        brief = _make_brief()
        analysis = HeuristicAnalyzer().analyze(brief)
        # sparkling-water has no hero_image → should have enrichment
        assert "sparkling-water" in analysis.prompt_enrichments

    def test_no_enrichment_for_existing_heroes(self):
        """Products with hero_image don't need enrichment."""
        brief = _make_brief()
        analysis = HeuristicAnalyzer().analyze(brief)
        # green-smoothie has a hero_image → should NOT have enrichment
        assert "green-smoothie" not in analysis.prompt_enrichments

    def test_creative_direction_generated(self):
        brief = _make_brief()
        analysis = HeuristicAnalyzer().analyze(brief)
        assert analysis.creative_direction
        assert "Recommended direction:" in analysis.creative_direction

    def test_detects_sensitive_campaign_message(self):
        brief = _make_brief(message="Get the BEST deal guaranteed!")
        analysis = HeuristicAnalyzer().analyze(brief)
        assert any("guaranteed" in r.lower() or "best" in r.lower() for r in analysis.risk_flags)

    def test_scores_audience_specificity(self):
        """Vague audiences should score lower on clarity."""
        vague = _make_brief(target_audience="Everyone")
        specific = _make_brief(target_audience="Health-conscious millennials, ages 22-38")
        vague_analysis = HeuristicAnalyzer().analyze(vague)
        specific_analysis = HeuristicAnalyzer().analyze(specific)
        assert specific_analysis.score.clarity > vague_analysis.score.clarity

    def test_platform_coverage_detected(self):
        """Full platform coverage (1:1, 9:16, 16:9) should be a strength."""
        brief = _make_brief()
        analysis = HeuristicAnalyzer().analyze(brief)
        assert any("platform coverage" in s.lower() for s in analysis.strengths)


class TestAnalyzeBrief:
    def test_default_uses_heuristic(self):
        brief = _make_brief()
        analysis = analyze_brief(brief)
        assert analysis.analyzed_by == "heuristic"

    def test_llm_mode_falls_back_without_key(self, monkeypatch):
        """Without an API key, LLM mode should fall back to heuristic."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        brief = _make_brief()
        analysis = analyze_brief(brief, use_llm=True)
        assert analysis.analyzed_by == "heuristic"


class TestMinimalBrief:
    def test_minimal_brief_still_analyzable(self):
        """Even a bare-minimum brief should produce a valid analysis."""
        brief = CampaignBrief(
            name="Test",
            brand="B",
            message="Buy",
            target_region="US",
            target_audience="Everyone",
            products=[
                Product(id="a", name="A", description="Product A"),
                Product(id="b", name="B", description="Product B"),
            ],
        )
        analysis = HeuristicAnalyzer().analyze(brief)
        assert analysis.score.overall > 0
        assert analysis.score.overall < 100
        assert len(analysis.weaknesses) > 0  # Minimal brief should have weaknesses
