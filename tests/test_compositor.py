"""Tests for image composition — layout quality, text rendering, branding.

These are contract tests that verify the compositor produces creatives
with the correct dimensions, proper text content, and brand elements (Fix 7).
"""

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from src.compositor import Compositor, TranslationProvider, get_translator


@pytest.fixture
def hero_1x1(tmp_path) -> Path:
    """Create a 1:1 test hero image."""
    img = Image.new("RGBA", (500, 500), (100, 150, 200, 255))
    p = tmp_path / "hero.png"
    img.save(str(p))
    return p


@pytest.fixture
def hero_wide(tmp_path) -> Path:
    """Create a 16:9 test hero image."""
    img = Image.new("RGBA", (960, 540), (100, 150, 200, 255))
    p = tmp_path / "hero_wide.png"
    img.save(str(p))
    return p


class TestOutputDimensions:
    """Verify creatives are produced at exact target dimensions."""

    def test_1x1_output(self, hero_1x1, tmp_path):
        comp = Compositor()
        out = tmp_path / "out.jpg"
        comp.compose(hero_1x1, out, 1080, 1080, "Test message")
        img = Image.open(str(out))
        assert img.size == (1080, 1080)

    def test_9x16_output(self, hero_1x1, tmp_path):
        comp = Compositor()
        out = tmp_path / "out.jpg"
        comp.compose(hero_1x1, out, 1080, 1920, "Test message")
        img = Image.open(str(out))
        assert img.size == (1080, 1920)

    def test_16x9_output(self, hero_wide, tmp_path):
        comp = Compositor()
        out = tmp_path / "out.jpg"
        comp.compose(hero_wide, out, 1920, 1080, "Test message")
        img = Image.open(str(out))
        assert img.size == (1920, 1080)


class TestRenderedTexts:
    """Verify compose() returns the list of all text actually drawn."""

    def test_returns_campaign_message(self, hero_1x1, tmp_path):
        comp = Compositor()
        _, texts = comp.compose(
            hero_1x1, tmp_path / "out.jpg", 400, 400,
            campaign_message="Stay Fresh",
        )
        assert "Stay Fresh" in texts

    def test_returns_brand_name(self, hero_1x1, tmp_path):
        comp = Compositor()
        _, texts = comp.compose(
            hero_1x1, tmp_path / "out.jpg", 400, 400,
            campaign_message="Msg", brand_name="FreshCo",
        )
        assert "FRESHCO" in texts

    def test_returns_tagline(self, hero_1x1, tmp_path):
        comp = Compositor()
        _, texts = comp.compose(
            hero_1x1, tmp_path / "out.jpg", 400, 400,
            campaign_message="Msg", tagline="Naturally Refreshing",
        )
        assert "Naturally Refreshing" in texts

    def test_returns_disclaimer(self, hero_1x1, tmp_path):
        comp = Compositor(required_disclaimer="Terms apply.")
        _, texts = comp.compose(
            hero_1x1, tmp_path / "out.jpg", 400, 400,
            campaign_message="Msg",
        )
        assert "Terms apply." in texts

    def test_no_disclaimer_when_not_configured(self, hero_1x1, tmp_path):
        comp = Compositor(required_disclaimer=None)
        _, texts = comp.compose(
            hero_1x1, tmp_path / "out.jpg", 400, 400,
            campaign_message="Msg",
        )
        assert not any("Terms" in t for t in texts)


class TestLogoPlacement:
    def test_logo_placed_flag(self, hero_1x1, tmp_path):
        """Compositor should track whether logo was actually placed."""
        comp = Compositor(logo_path="input_assets/logo.png")
        comp.compose(hero_1x1, tmp_path / "out.jpg", 400, 400, "Msg")
        assert comp.logo_placed is True

    def test_no_logo_flag_when_missing(self, hero_1x1, tmp_path):
        comp = Compositor(logo_path=None)
        comp.compose(hero_1x1, tmp_path / "out.jpg", 400, 400, "Msg")
        assert comp.logo_placed is False

    def test_no_logo_flag_when_file_missing(self, hero_1x1, tmp_path):
        comp = Compositor(logo_path="/nonexistent/logo.png")
        comp.compose(hero_1x1, tmp_path / "out.jpg", 400, 400, "Msg")
        assert comp.logo_placed is False


class TestBrandConfig:
    """Verify compositor uses configured brand parameters."""

    def test_accent_color_used(self, hero_1x1, tmp_path):
        """Accent color should affect the bottom accent bar."""
        comp = Compositor(
            brand_colors=["#000000"],
            accent_color="#FF0000",
        )
        out = tmp_path / "out.jpg"
        comp.compose(hero_1x1, out, 400, 400, "Msg")
        img = Image.open(str(out))
        # Sample bottom-right pixel (accent bar area)
        bottom_pixel = img.getpixel((200, 399))
        # Should have red channel dominant (from #FF0000 accent)
        assert bottom_pixel[0] > 200  # Red channel high

    def test_primary_color_fallback_when_no_accent(self, hero_1x1, tmp_path):
        """Without accent_color, primary_colors[0] should be used."""
        comp = Compositor(brand_colors=["#0000FF"], accent_color=None)
        out = tmp_path / "out.jpg"
        comp.compose(hero_1x1, out, 400, 400, "Msg")
        img = Image.open(str(out))
        bottom_pixel = img.getpixel((200, 399))
        # Should have blue channel dominant
        assert bottom_pixel[2] > 200


# ---------------------------------------------------------------------------
# Translation provider tests
# ---------------------------------------------------------------------------

class TestTranslationProvider:
    def test_english_passthrough(self):
        tp = TranslationProvider()
        text, ok = tp.translate("Anything", "en")
        assert text == "Anything"
        assert ok is True

    def test_known_translation(self):
        tp = TranslationProvider()
        text, ok = tp.translate("Stay Fresh This Summer", "es")
        assert text == "Mantente Fresco Este Verano"
        assert ok is True
        assert len(tp.warnings) == 0

    def test_unknown_message_returns_source_with_warning(self):
        tp = TranslationProvider()
        tp.clear_warnings()
        text, ok = tp.translate("Completely new copy not in table", "fr")
        assert text == "Completely new copy not in table"  # Source returned
        assert ok is False
        assert len(tp.warnings) == 1
        assert "TMS" in tp.warnings[0]  # Suggests TMS review

    def test_unknown_language_for_known_message(self):
        tp = TranslationProvider()
        tp.clear_warnings()
        text, ok = tp.translate("Stay Fresh This Summer", "ko")
        assert ok is False
        assert text == "Stay Fresh This Summer"
        assert len(tp.warnings) == 1

    def test_tagline_translation(self):
        tp = TranslationProvider()
        text, ok = tp.translate("Naturally Refreshing", "es")
        assert text == "Naturalmente Refrescante"
        assert ok is True
