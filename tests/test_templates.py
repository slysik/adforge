"""Tests for the multi-template layout system."""

from pathlib import Path

import pytest
from PIL import Image

from src.templates import (
    LayoutTemplate, auto_select_template,
    render_product_hero, render_editorial, render_split_panel,
    render_minimal, render_bold_type, TEMPLATE_RENDERERS,
)


@pytest.fixture
def hero_img() -> Image.Image:
    """Create a test hero image."""
    return Image.new("RGBA", (500, 500), (100, 150, 200, 255))


class TestAutoSelect:
    def test_luxury_keywords_select_minimal(self):
        t = auto_select_template("1:1", ["luxury", "gold", "serum"], "Message")
        assert t == LayoutTemplate.MINIMAL

    def test_short_message_selects_bold_type(self):
        t = auto_select_template("1:1", ["basic"], "Buy Now")
        assert t == LayoutTemplate.BOLD_TYPE

    def test_vertical_format_selects_split_panel(self):
        t = auto_select_template("9:16", ["product"], "A longer campaign message here")
        assert t == LayoutTemplate.SPLIT_PANEL

    def test_long_message_selects_editorial(self):
        t = auto_select_template("1:1", ["basic"],
                                 "This is a very long campaign message that needs editorial layout")
        assert t == LayoutTemplate.EDITORIAL

    def test_default_selects_product_hero(self):
        t = auto_select_template("1:1", ["basic"], "Medium length message here")
        assert t == LayoutTemplate.PRODUCT_HERO


class TestTemplateRegistry:
    def test_all_templates_registered(self):
        """Every LayoutTemplate enum value should have a renderer."""
        for template in LayoutTemplate:
            assert template in TEMPLATE_RENDERERS, f"Missing renderer for {template}"


class TestProductHeroTemplate:
    def test_produces_correct_dimensions(self, hero_img):
        canvas, texts = render_product_hero(
            hero_img, 1080, 1080, "Campaign Message", "Tagline",
            "Brand", "Arial", ["#000000"], None,
        )
        assert canvas.size == (1080, 1080)

    def test_renders_message(self, hero_img):
        _, texts = render_product_hero(
            hero_img, 500, 500, "Stay Fresh", "Cool tagline",
            "FreshCo", "Arial", ["#000000"], None,
        )
        assert "Stay Fresh" in texts

    def test_renders_brand_and_tagline(self, hero_img):
        _, texts = render_product_hero(
            hero_img, 500, 500, "Msg", "My Tagline",
            "BrandName", "Arial", ["#000000"], None,
        )
        assert "BRANDNAME" in texts
        assert "My Tagline" in texts


class TestEditorialTemplate:
    def test_produces_correct_dimensions(self, hero_img):
        canvas, _ = render_editorial(
            hero_img, 1920, 1080, "Message", None,
            "Brand", "Arial", ["#1A1A2E"], None,
        )
        assert canvas.size == (1920, 1080)

    def test_renders_message(self, hero_img):
        _, texts = render_editorial(
            hero_img, 500, 500, "Editorial Message", None,
            "Brand", "Arial", ["#1A1A2E"], None,
        )
        assert "Editorial Message" in texts


class TestSplitPanelTemplate:
    def test_vertical_produces_correct_dimensions(self, hero_img):
        canvas, _ = render_split_panel(
            hero_img, 1080, 1920, "Message", None,
            "Brand", "Arial", ["#1A1A2E"], None,
        )
        assert canvas.size == (1080, 1920)

    def test_horizontal_produces_correct_dimensions(self, hero_img):
        canvas, _ = render_split_panel(
            hero_img, 1920, 1080, "Message", None,
            "Brand", "Arial", ["#1A1A2E"], None,
        )
        assert canvas.size == (1920, 1080)


class TestMinimalTemplate:
    def test_produces_correct_dimensions(self, hero_img):
        canvas, _ = render_minimal(
            hero_img, 1080, 1080, "Premium Product", None,
            "LuxeBrand", "Georgia", ["#C9A96E"], None,
        )
        assert canvas.size == (1080, 1080)

    def test_renders_message_and_brand(self, hero_img):
        _, texts = render_minimal(
            hero_img, 500, 500, "Premium Feel", "Elegant",
            "Luxe", "Georgia", ["#C9A96E"], None,
        )
        assert "Premium Feel" in texts
        assert "LUXE" in texts


class TestBoldTypeTemplate:
    def test_produces_correct_dimensions(self, hero_img):
        canvas, _ = render_bold_type(
            hero_img, 1080, 1920, "BOLD", None,
            "Brand", "Arial", ["#000000"], "#FF0000",
        )
        assert canvas.size == (1080, 1920)

    def test_renders_message(self, hero_img):
        _, texts = render_bold_type(
            hero_img, 500, 500, "Big Text", None,
            "Brand", "Arial", ["#000000"], None,
        )
        assert "Big Text" in texts
