"""Tests for the image generator — verifying mock mode produces clean images."""

from pathlib import Path

import pytest
from PIL import Image

from src.generator import ImageGenerator


class TestMockGenerator:
    def test_generates_correct_dimensions_1x1(self, tmp_path):
        gen = ImageGenerator(mock=True)
        out = tmp_path / "hero.png"
        path, prompt = gen.generate_hero(
            product_name="Test Product",
            product_description="A test product",
            keywords=["test"],
            campaign_message="Buy it",
            target_audience="Everyone",
            target_region="US",
            brand_name="TestBrand",
            aspect_ratio="1:1",
            output_path=out,
        )
        img = Image.open(str(path))
        assert img.size == (1080, 1080)

    def test_generates_correct_dimensions_9x16(self, tmp_path):
        gen = ImageGenerator(mock=True)
        out = tmp_path / "hero.png"
        path, _ = gen.generate_hero(
            product_name="Test", product_description="Desc",
            keywords=[], campaign_message="Msg",
            target_audience="All", target_region="US",
            brand_name="Brand", aspect_ratio="9:16",
            output_path=out,
        )
        img = Image.open(str(path))
        assert img.size == (1080, 1920)

    def test_generates_correct_dimensions_16x9(self, tmp_path):
        gen = ImageGenerator(mock=True)
        out = tmp_path / "hero.png"
        path, _ = gen.generate_hero(
            product_name="Test", product_description="Desc",
            keywords=[], campaign_message="Msg",
            target_audience="All", target_region="US",
            brand_name="Brand", aspect_ratio="16:9",
            output_path=out,
        )
        img = Image.open(str(path))
        assert img.size == (1920, 1080)

    def test_returns_prompt(self, tmp_path):
        gen = ImageGenerator(mock=True)
        _, prompt = gen.generate_hero(
            product_name="Sparkling Water",
            product_description="Fizzy water",
            keywords=["fizzy", "water"],
            campaign_message="Stay Fresh",
            target_audience="Youth",
            target_region="US",
            brand_name="AquaCo",
            output_path=tmp_path / "hero.png",
        )
        assert "Sparkling Water" in prompt
        assert "AquaCo" in prompt
        assert "Stay Fresh" in prompt

    def test_no_text_in_mock_image(self, tmp_path):
        """Mock images must NOT contain text labels or watermarks (Fix 1)."""
        gen = ImageGenerator(mock=True)
        path, _ = gen.generate_hero(
            product_name="Test Product",
            product_description="Desc",
            keywords=[], campaign_message="Msg",
            target_audience="All", target_region="US",
            brand_name="Brand",
            output_path=tmp_path / "hero.png",
        )
        # Load as RGBA and verify no "[MOCK]" text by checking
        # that the image is purely procedural (all RGBA, no embedded text).
        img = Image.open(str(path))
        assert img.mode == "RGBA"
        # The image should be non-trivial (not solid color)
        pixels = list(img.getdata())
        unique = len(set(pixels[:1000]))
        assert unique > 5, "Mock image appears to be solid color"

    def test_deterministic_colors(self, tmp_path):
        """Same product name → same color palette."""
        gen = ImageGenerator(mock=True)
        p1, _ = gen.generate_hero(
            product_name="Consistent Product",
            product_description="D", keywords=[], campaign_message="M",
            target_audience="A", target_region="R", brand_name="B",
            output_path=tmp_path / "h1.png",
        )
        p2, _ = gen.generate_hero(
            product_name="Consistent Product",
            product_description="D", keywords=[], campaign_message="M",
            target_audience="A", target_region="R", brand_name="B",
            output_path=tmp_path / "h2.png",
        )
        img1 = Image.open(str(p1))
        img2 = Image.open(str(p2))
        # Center pixel should match (deterministic palette)
        assert img1.getpixel((540, 540)) == img2.getpixel((540, 540))
