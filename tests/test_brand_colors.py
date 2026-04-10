"""Tests that brand colors propagate correctly to all template renderers."""

from pathlib import Path

import pytest
from PIL import Image

from src.templates import (
    render_product_hero,
    render_editorial,
    render_split_panel,
    render_minimal,
    render_bold_type,
)
from src.compositor import _hex_to_rgb


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

BRAND_COLORS = ["#FF0000", "#00FF00"]
ACCENT_COLOR = "#0000FF"
WIDTH, HEIGHT = 400, 400


@pytest.fixture
def hero_img() -> Image.Image:
    """Solid mid-gray hero so brand colors are easy to detect."""
    return Image.new("RGBA", (400, 400), (128, 128, 128, 255))


def _pixel_rgb(canvas: Image.Image, x: int, y: int) -> tuple[int, int, int]:
    """Return the RGB values of a pixel (drop alpha)."""
    r, g, b, *_ = canvas.getpixel((x, y))
    return (r, g, b)


def _color_close(actual: tuple[int, int, int], expected: tuple[int, int, int], tolerance: int = 40) -> bool:
    """Check if two RGB colors are within tolerance per channel."""
    return all(abs(a - e) <= tolerance for a, e in zip(actual, expected))


# ---------------------------------------------------------------------------
# render_product_hero — should now have an accent bar at bottom
# ---------------------------------------------------------------------------

class TestProductHeroBrandColors:
    def test_accent_bar_with_accent_color(self, hero_img):
        """When accent_color is given, the bottom accent bar uses it."""
        canvas, _ = render_product_hero(
            hero_img, WIDTH, HEIGHT, "Message", None,
            "Brand", "Arial", BRAND_COLORS, ACCENT_COLOR,
        )
        # Sample bottom pixels — accent bar is 4px tall
        pixel = _pixel_rgb(canvas, WIDTH // 2, HEIGHT - 2)
        expected = _hex_to_rgb(ACCENT_COLOR)  # (0, 0, 255)
        assert _color_close(pixel, expected), (
            f"Expected accent bar near {expected}, got {pixel}"
        )

    def test_accent_bar_fallback_to_brand_color(self, hero_img):
        """When no accent_color, bar falls back to brand_colors[0]."""
        canvas, _ = render_product_hero(
            hero_img, WIDTH, HEIGHT, "Message", None,
            "Brand", "Arial", BRAND_COLORS, None,
        )
        pixel = _pixel_rgb(canvas, WIDTH // 2, HEIGHT - 2)
        expected = _hex_to_rgb(BRAND_COLORS[0])  # (255, 0, 0)
        assert _color_close(pixel, expected), (
            f"Expected brand bar near {expected}, got {pixel}"
        )


# ---------------------------------------------------------------------------
# render_editorial — brand_colors[0] panel + accent separator
# ---------------------------------------------------------------------------

class TestEditorialBrandColors:
    def test_panel_uses_brand_color(self, hero_img):
        """Text panel below hero should use brand_colors[0]."""
        canvas, _ = render_editorial(
            hero_img, WIDTH, HEIGHT, "Message", None,
            "Brand", "Arial", BRAND_COLORS, ACCENT_COLOR,
        )
        # Panel starts at 60% height, sample mid-panel
        panel_y = int(HEIGHT * 0.8)
        pixel = _pixel_rgb(canvas, WIDTH // 2, panel_y)
        expected = _hex_to_rgb(BRAND_COLORS[0])
        assert _color_close(pixel, expected, tolerance=50), (
            f"Expected panel near {expected}, got {pixel}"
        )

    def test_accent_separator_line(self, hero_img):
        """Accent separator line at the hero/panel boundary."""
        canvas, _ = render_editorial(
            hero_img, WIDTH, HEIGHT, "Message", None,
            "Brand", "Arial", BRAND_COLORS, ACCENT_COLOR,
        )
        hero_h = int(HEIGHT * 0.6)
        pixel = _pixel_rgb(canvas, WIDTH // 2, hero_h + 2)
        expected = _hex_to_rgb(ACCENT_COLOR)
        assert _color_close(pixel, expected), (
            f"Expected accent separator near {expected}, got {pixel}"
        )


# ---------------------------------------------------------------------------
# render_split_panel — panel uses darkest brand color, accent bar
# ---------------------------------------------------------------------------

class TestSplitPanelBrandColors:
    def test_panel_uses_brand_color(self, hero_img):
        """Right panel (horizontal) should use a brand color."""
        canvas, _ = render_split_panel(
            hero_img, WIDTH, HEIGHT, "Message", None,
            "Brand", "Arial", BRAND_COLORS, ACCENT_COLOR,
        )
        # Horizontal split: right panel starts at WIDTH//2
        panel_x = WIDTH * 3 // 4
        panel_y = HEIGHT // 2
        pixel = _pixel_rgb(canvas, panel_x, panel_y)
        # _pick_panel_color picks the darkest brand color
        # #FF0000 luminance ~ 0.21, #00FF00 luminance ~ 0.72 => picks red
        expected = _hex_to_rgb(BRAND_COLORS[0])
        assert _color_close(pixel, expected, tolerance=50), (
            f"Expected panel near {expected}, got {pixel}"
        )


# ---------------------------------------------------------------------------
# render_minimal — text color uses brand_colors[0]
# ---------------------------------------------------------------------------

class TestMinimalBrandColors:
    def test_text_uses_brand_color(self, hero_img):
        """Message text should be rendered in brand_colors[0]."""
        canvas, _ = render_minimal(
            hero_img, WIDTH, HEIGHT, "Test", None,
            "Brand", "Arial", BRAND_COLORS, ACCENT_COLOR,
        )
        # The canvas is mostly warm-white background; scan a region below
        # the hero area for non-white, non-gray pixels that match brand color.
        brand_rgb = _hex_to_rgb(BRAND_COLORS[0])
        found = False
        # Text appears below hero (hero_y + hero_h ~ 0.08*H + 0.6*H = 0.68*H)
        scan_y_start = int(HEIGHT * 0.70)
        scan_y_end = int(HEIGHT * 0.90)
        for y in range(scan_y_start, scan_y_end):
            for x in range(0, WIDTH, 4):
                pixel = _pixel_rgb(canvas, x, y)
                if _color_close(pixel, brand_rgb, tolerance=50):
                    found = True
                    break
            if found:
                break
        assert found, f"Expected to find brand color {brand_rgb} in text area"


# ---------------------------------------------------------------------------
# render_bold_type — accent_color for tint/underline, fallback to brand_colors[0]
# ---------------------------------------------------------------------------

class TestBoldTypeBrandColors:
    def test_accent_underline_with_accent_color(self, hero_img):
        """When accent_color is given, underline uses it."""
        canvas, _ = render_bold_type(
            hero_img, WIDTH, HEIGHT, "Bold", None,
            "Brand", "Arial", BRAND_COLORS, ACCENT_COLOR,
        )
        # Scan for blue-ish pixels in the middle area (underline)
        accent_rgb = _hex_to_rgb(ACCENT_COLOR)
        found = False
        for y in range(HEIGHT // 3, HEIGHT * 2 // 3):
            for x in range(0, WIDTH, 4):
                pixel = _pixel_rgb(canvas, x, y)
                if _color_close(pixel, accent_rgb, tolerance=50):
                    found = True
                    break
            if found:
                break
        assert found, f"Expected accent underline with color {accent_rgb}"

    def test_fallback_to_brand_color_when_no_accent(self, hero_img):
        """When no accent_color, bold_type uses brand_colors[0] for tint and underline."""
        canvas, _ = render_bold_type(
            hero_img, WIDTH, HEIGHT, "Bold", None,
            "Brand", "Arial", BRAND_COLORS, None,
        )
        # The underline should now use brand_colors[0] = red
        brand_rgb = _hex_to_rgb(BRAND_COLORS[0])
        found = False
        for y in range(HEIGHT // 3, HEIGHT * 2 // 3):
            for x in range(0, WIDTH, 4):
                pixel = _pixel_rgb(canvas, x, y)
                if _color_close(pixel, brand_rgb, tolerance=50):
                    found = True
                    break
            if found:
                break
        assert found, (
            f"Expected brand_colors[0] fallback ({brand_rgb}) for underline when no accent_color"
        )
