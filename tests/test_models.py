"""Tests for campaign brief models and schema enforcement."""

import pytest
from src.models import (
    CampaignBrief, Product, AspectRatio, BrandGuidelines,
    ComplianceStatus, ComplianceResult,
)


# ---------------------------------------------------------------------------
# Valid brief helper
# ---------------------------------------------------------------------------

def _make_brief(**overrides):
    """Create a valid brief with optional overrides."""
    defaults = dict(
        name="Test Campaign",
        brand="TestBrand",
        message="Test message",
        target_region="US",
        target_audience="Everyone",
        products=[
            Product(id="prod-a", name="Product A", description="First product"),
            Product(id="prod-b", name="Product B", description="Second product"),
        ],
    )
    defaults.update(overrides)
    return CampaignBrief(**defaults)


# ---------------------------------------------------------------------------
# Schema enforcement (Fix 3)
# ---------------------------------------------------------------------------

class TestBriefEnforcement:
    def test_valid_brief(self):
        brief = _make_brief()
        assert brief.name == "Test Campaign"
        assert len(brief.products) == 2
        assert len(brief.aspect_ratios) == 3  # defaults

    def test_requires_minimum_two_products(self):
        """Exercise requirement: at least two products."""
        with pytest.raises(Exception, match="least 2"):
            _make_brief(products=[
                Product(id="only-one", name="Solo", description="Single product"),
            ])

    def test_empty_products_rejected(self):
        with pytest.raises(Exception):
            _make_brief(products=[])

    def test_requires_minimum_three_aspect_ratios(self):
        """Exercise requirement: at least three aspect ratios."""
        with pytest.raises(Exception, match="least 3"):
            _make_brief(aspect_ratios=[
                AspectRatio(name="a", ratio="1:1", width=100, height=100),
                AspectRatio(name="b", ratio="16:9", width=160, height=90),
            ])

    def test_duplicate_product_ids_rejected(self):
        with pytest.raises(Exception, match="[Dd]uplicate"):
            _make_brief(products=[
                Product(id="same-id", name="A", description="First"),
                Product(id="same-id", name="B", description="Second"),
            ])

    def test_invalid_hex_color_rejected(self):
        with pytest.raises(Exception, match="[Hh]ex"):
            _make_brief(
                brand_guidelines=BrandGuidelines(primary_colors=["red", "blue"]),
            )

    def test_valid_hex_colors_accepted(self):
        brief = _make_brief(
            brand_guidelines=BrandGuidelines(
                primary_colors=["#FF0000", "#00FF00", "#0000FF"],
            ),
        )
        assert len(brief.brand_guidelines.primary_colors) == 3

    def test_invalid_accent_color_rejected(self):
        with pytest.raises(Exception, match="[Hh]ex"):
            _make_brief(
                brand_guidelines=BrandGuidelines(accent_color="gold"),
            )

    def test_invalid_language_rejected(self):
        with pytest.raises(Exception, match="[Uu]nsupported"):
            _make_brief(languages=["en", "klingon"])

    def test_duplicate_languages_rejected(self):
        with pytest.raises(Exception, match="[Dd]uplicate"):
            _make_brief(languages=["en", "en"])

    def test_empty_languages_rejected(self):
        with pytest.raises(Exception):
            _make_brief(languages=[])

    def test_product_id_format_enforced(self):
        """Product IDs must be lowercase slugs."""
        with pytest.raises(Exception):
            Product(id="UPPER CASE!", name="Bad", description="Invalid id")

    def test_aspect_ratio_format_enforced(self):
        """Ratio must match N:M pattern."""
        with pytest.raises(Exception):
            AspectRatio(name="bad", ratio="square", width=100, height=100)


# ---------------------------------------------------------------------------
# Brand guidelines defaults
# ---------------------------------------------------------------------------

class TestBrandGuidelines:
    def test_defaults(self):
        bg = BrandGuidelines()
        assert len(bg.primary_colors) == 2
        assert bg.prohibited_words == []
        assert bg.font_family == "Arial"
        assert bg.required_disclaimer is None

    def test_all_fields_settable(self):
        bg = BrandGuidelines(
            primary_colors=["#000000"],
            accent_color="#FFD700",
            font_family="Georgia",
            required_disclaimer="Terms apply.",
            prohibited_words=["bad"],
        )
        assert bg.accent_color == "#FFD700"
        assert bg.required_disclaimer == "Terms apply."


# ---------------------------------------------------------------------------
# Compliance result model
# ---------------------------------------------------------------------------

class TestComplianceResult:
    def test_default_not_checked(self):
        cr = ComplianceResult(status=ComplianceStatus.NOT_CHECKED)
        assert cr.status == ComplianceStatus.NOT_CHECKED
        assert cr.notes == []

    def test_passed_with_notes(self):
        cr = ComplianceResult(
            status=ComplianceStatus.PASSED,
            notes=["All checks passed."],
        )
        assert cr.status == ComplianceStatus.PASSED

    def test_all_statuses_serializable(self):
        for s in ComplianceStatus:
            cr = ComplianceResult(status=s, notes=[f"status={s.value}"])
            d = cr.model_dump()
            assert d["status"] == s.value
