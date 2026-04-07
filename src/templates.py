"""
Multi-template layout system for campaign creatives.

Real creative teams use different layouts for different placements and
campaign goals. This module provides multiple layout templates that the
pipeline can select automatically or via brief configuration.

Templates:
  - PRODUCT_HERO: Product-centric with bold messaging (default)
  - EDITORIAL: Text-forward with editorial feel
  - SPLIT_PANEL: 50/50 image/text split
  - MINIMAL: Clean, whitespace-heavy, premium feel
  - BOLD_TYPE: Oversized typography with subtle background

Each template is a composition strategy — it takes the same inputs
(hero image, text, brand config) and produces a different visual layout.
This is how production creative automation works at scale.
"""

from __future__ import annotations

import textwrap
from enum import Enum
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from rich.console import Console

from .compositor import (
    _get_font, _get_cjk_font, _needs_cjk,
    _hex_to_rgb, _draw_text_with_shadow, _draw_gradient_overlay,
)

console = Console()


class LayoutTemplate(str, Enum):
    """Available layout templates for creative composition."""
    PRODUCT_HERO = "product_hero"    # Default: full-bleed hero with overlay text
    EDITORIAL = "editorial"          # Text-forward, editorial magazine feel
    SPLIT_PANEL = "split_panel"      # 50/50 image and text panel
    MINIMAL = "minimal"              # Clean, premium, whitespace-heavy
    BOLD_TYPE = "bold_type"          # Oversized typography focus


def auto_select_template(
    aspect_ratio: str,
    product_keywords: list[str],
    campaign_message: str,
) -> LayoutTemplate:
    """Automatically select the best template based on content signals.

    This encodes creative judgment as a heuristic:
      - Stories/vertical formats → BOLD_TYPE (typography dominates vertical space)
      - Luxury/premium keywords → MINIMAL (premium feel)
      - Short punchy messages → BOLD_TYPE
      - Long messages → EDITORIAL (more text room)
      - Default → PRODUCT_HERO (universally safe)
    """
    luxury_keywords = {"luxury", "premium", "gold", "velvet", "serum", "radiance", "elegant"}
    has_luxury = bool(set(k.lower() for k in product_keywords) & luxury_keywords)

    if has_luxury:
        return LayoutTemplate.MINIMAL

    if len(campaign_message) <= 20:
        return LayoutTemplate.BOLD_TYPE

    if aspect_ratio == "9:16":
        return LayoutTemplate.SPLIT_PANEL

    if len(campaign_message) > 40:
        return LayoutTemplate.EDITORIAL

    return LayoutTemplate.PRODUCT_HERO


# ---------------------------------------------------------------------------
# Template renderers
# ---------------------------------------------------------------------------

def render_product_hero(
    hero: Image.Image,
    width: int,
    height: int,
    message: str,
    tagline: Optional[str],
    brand_name: str,
    font_family: str,
    brand_colors: list[str],
    accent_color: Optional[str],
) -> tuple[Image.Image, list[str]]:
    """Full-bleed hero with gradient overlay and text at bottom.
    This is the default template — universally safe for all placements.
    """
    rendered = []
    canvas = _smart_resize(hero, width, height)
    canvas = _draw_gradient_overlay(canvas, "bottom", opacity=190)

    draw = ImageDraw.Draw(canvas)
    base = min(width, height)
    padding = int(width * 0.06)

    # Brand name (top)
    if brand_name:
        brand_font = _get_font(font_family, max(16, int(base * 0.028)))
        brand_text = brand_name.upper()
        _draw_text_with_shadow(draw, (padding, padding), brand_text,
                               brand_font, (255, 255, 255, 220), shadow_offset=2)
        rendered.append(brand_text)

    # Message + tagline (bottom)
    msg_font = _get_cjk_font(max(28, int(base * 0.065))) if _needs_cjk(message) else _get_font(font_family, max(28, int(base * 0.065)))
    tag_font = _get_font(font_family, max(18, int(base * 0.035)))

    y_cursor = height - padding
    if tagline:
        tag_bbox = draw.textbbox((0, 0), tagline, font=tag_font)
        y_cursor -= (tag_bbox[3] - tag_bbox[1]) + 10
        _draw_text_with_shadow(draw, (padding, y_cursor), tagline,
                               tag_font, (255, 255, 255, 200), shadow_offset=2)
        rendered.append(tagline)

    max_chars = max(15, int(width / (max(28, int(base * 0.065)) * 0.55)))
    lines = textwrap.wrap(message, width=max_chars)
    text_block = "\n".join(lines)
    msg_bbox = draw.multiline_textbbox((0, 0), text_block, font=msg_font)
    y_cursor -= (msg_bbox[3] - msg_bbox[1]) + 15

    for line in lines:
        _draw_text_with_shadow(draw, (padding, y_cursor), line,
                               msg_font, (255, 255, 255, 255), shadow_offset=3)
        line_bbox = draw.textbbox((0, 0), line, font=msg_font)
        y_cursor += (line_bbox[3] - line_bbox[1]) + 8

    rendered.append(message)
    return canvas, rendered


def render_editorial(
    hero: Image.Image,
    width: int,
    height: int,
    message: str,
    tagline: Optional[str],
    brand_name: str,
    font_family: str,
    brand_colors: list[str],
    accent_color: Optional[str],
) -> tuple[Image.Image, list[str]]:
    """Editorial layout: hero takes top 60%, text block on colored panel below."""
    rendered = []

    # Split: 60% hero, 40% text panel
    hero_h = int(height * 0.6)
    panel_h = height - hero_h

    # Hero area
    canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
    hero_resized = _smart_resize(hero, width, hero_h)
    canvas.paste(hero_resized, (0, 0))

    # Text panel with brand color
    panel_color = _hex_to_rgb(brand_colors[0]) if brand_colors else (30, 30, 30)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([(0, hero_h), (width, height)], fill=panel_color + (245,))

    # Accent line separator
    if accent_color:
        accent_rgb = _hex_to_rgb(accent_color)
        draw.rectangle([(0, hero_h), (width, hero_h + 4)], fill=accent_rgb + (255,))

    base = min(width, height)
    padding = int(width * 0.06)
    text_y = hero_h + int(panel_h * 0.15)

    # Brand name
    if brand_name:
        brand_font = _get_font(font_family, max(14, int(base * 0.022)))
        brand_text = brand_name.upper()
        draw.text((padding, text_y), brand_text, font=brand_font, fill=(255, 255, 255, 180))
        rendered.append(brand_text)
        text_y += int(base * 0.04)

    # Message
    msg_size = max(24, int(base * 0.055))
    msg_font = _get_cjk_font(msg_size) if _needs_cjk(message) else _get_font(font_family, msg_size)
    max_chars = max(15, int(width / (msg_size * 0.55)))
    lines = textwrap.wrap(message, width=max_chars)

    for line in lines:
        draw.text((padding, text_y), line, font=msg_font, fill=(255, 255, 255, 255))
        line_bbox = draw.textbbox((0, 0), line, font=msg_font)
        text_y += (line_bbox[3] - line_bbox[1]) + 6

    rendered.append(message)

    # Tagline
    if tagline:
        text_y += 8
        tag_font = _get_font(font_family, max(16, int(base * 0.028)))
        draw.text((padding, text_y), tagline, font=tag_font, fill=(255, 255, 255, 180))
        rendered.append(tagline)

    return canvas, rendered


def _luminance(rgb: tuple[int, int, int]) -> float:
    """Compute relative luminance of an RGB color (0.0=black, 1.0=white)."""
    r, g, b = [c / 255.0 for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _pick_panel_color(brand_colors: list[str]) -> tuple[int, int, int]:
    """Pick the darkest brand color for panel backgrounds.

    Uses the color with the lowest luminance so that white text
    is always readable. Falls back to near-black if no dark color
    is available.
    """
    if not brand_colors:
        return (30, 30, 30)
    candidates = [_hex_to_rgb(c) for c in brand_colors]
    # Sort by luminance ascending (darkest first)
    candidates.sort(key=lambda c: _luminance(c))
    # Use the darkest color; if it's still too light, fall back
    darkest = candidates[0]
    if _luminance(darkest) > 0.6:
        return (30, 30, 30)  # safety fallback for all-light palettes
    return darkest


def render_split_panel(
    hero: Image.Image,
    width: int,
    height: int,
    message: str,
    tagline: Optional[str],
    brand_name: str,
    font_family: str,
    brand_colors: list[str],
    accent_color: Optional[str],
) -> tuple[Image.Image, list[str]]:
    """50/50 split: image on left/top, branded text panel on right/bottom.

    Panel color is the *darkest* brand color so that white text
    is always readable — avoids the white-on-white bug.
    """
    rendered = []
    is_vertical = height > width
    panel_color = _pick_panel_color(brand_colors)

    if is_vertical:
        # Top/bottom split for vertical formats
        img_h = height // 2
        panel_h = height - img_h

        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        hero_resized = _smart_resize(hero, width, img_h)
        canvas.paste(hero_resized, (0, 0))

        # Panel — always uses darkest brand color for contrast
        draw = ImageDraw.Draw(canvas)
        draw.rectangle([(0, img_h), (width, height)], fill=panel_color + (255,))

        padding = int(width * 0.08)
        text_y = img_h + int(panel_h * 0.12)
    else:
        # Left/right split for horizontal formats
        img_w = width // 2
        panel_w = width - img_w

        canvas = Image.new("RGBA", (width, height), (255, 255, 255, 255))
        hero_resized = _smart_resize(hero, img_w, height)
        canvas.paste(hero_resized, (0, 0))

        draw = ImageDraw.Draw(canvas)
        draw.rectangle([(img_w, 0), (width, height)], fill=panel_color + (255,))

        padding = img_w + int(panel_w * 0.08)
        text_y = int(height * 0.15)

    base = min(width, height)

    # Brand name
    if brand_name:
        brand_font = _get_font(font_family, max(14, int(base * 0.024)))
        brand_text = brand_name.upper()
        draw.text((padding, text_y), brand_text, font=brand_font, fill=(255, 255, 255, 180))
        rendered.append(brand_text)
        text_y += int(base * 0.05)

    # Accent bar
    if accent_color:
        accent_rgb = _hex_to_rgb(accent_color)
        bar_w = int(base * 0.15)
        draw.rectangle([(padding, text_y), (padding + bar_w, text_y + 3)], fill=accent_rgb + (255,))
        text_y += 15

    # Message
    msg_size = max(22, int(base * 0.05))
    msg_font = _get_cjk_font(msg_size) if _needs_cjk(message) else _get_font(font_family, msg_size)
    avail_w = (width - padding - int(width * 0.04)) if not is_vertical else (width - 2 * int(width * 0.08))
    max_chars = max(12, int(avail_w / (msg_size * 0.55)))
    lines = textwrap.wrap(message, width=max_chars)

    for line in lines:
        draw.text((padding, text_y), line, font=msg_font, fill=(255, 255, 255, 255))
        line_bbox = draw.textbbox((0, 0), line, font=msg_font)
        text_y += (line_bbox[3] - line_bbox[1]) + 6

    rendered.append(message)

    if tagline:
        text_y += 12
        tag_font = _get_font(font_family, max(14, int(base * 0.028)))
        draw.text((padding, text_y), tagline, font=tag_font, fill=(255, 255, 255, 160))
        rendered.append(tagline)

    return canvas, rendered


def render_minimal(
    hero: Image.Image,
    width: int,
    height: int,
    message: str,
    tagline: Optional[str],
    brand_name: str,
    font_family: str,
    brand_colors: list[str],
    accent_color: Optional[str],
) -> tuple[Image.Image, list[str]]:
    """Minimal/premium: centered hero at 60% scale, generous whitespace, refined type."""
    rendered = []

    # White canvas with subtle warm tint
    bg_color = (252, 250, 248, 255)  # Very slight warm white
    canvas = Image.new("RGBA", (width, height), bg_color)

    # Centered hero at 60% scale
    hero_scale = 0.6
    hero_w = int(width * hero_scale)
    hero_h = int(height * hero_scale)
    hero_resized = _smart_resize(hero, hero_w, hero_h)

    # Add subtle shadow behind hero
    shadow = Image.new("RGBA", (hero_w + 20, hero_h + 20), (0, 0, 0, 0))
    shadow_draw = ImageDraw.Draw(shadow)
    shadow_draw.rectangle([(10, 10), (hero_w + 10, hero_h + 10)], fill=(0, 0, 0, 30))
    shadow = shadow.filter(ImageFilter.GaussianBlur(radius=8))

    hero_x = (width - hero_w) // 2
    hero_y = int(height * 0.08)
    canvas.paste(shadow, (hero_x - 10, hero_y + 5), shadow)
    canvas.paste(hero_resized, (hero_x, hero_y), hero_resized)

    draw = ImageDraw.Draw(canvas)
    base = min(width, height)
    text_color = _hex_to_rgb(brand_colors[0]) if brand_colors else (30, 30, 30)

    # Message below hero, centered
    msg_y = hero_y + hero_h + int(height * 0.04)
    msg_size = max(22, int(base * 0.045))
    msg_font = _get_cjk_font(msg_size) if _needs_cjk(message) else _get_font(font_family, msg_size)
    max_chars = max(20, int(width / (msg_size * 0.55)))
    lines = textwrap.wrap(message, width=max_chars)

    for line in lines:
        line_bbox = draw.textbbox((0, 0), line, font=msg_font)
        lw = line_bbox[2] - line_bbox[0]
        draw.text(((width - lw) // 2, msg_y), line, font=msg_font, fill=text_color + (230,))
        msg_y += (line_bbox[3] - line_bbox[1]) + 6

    rendered.append(message)

    # Tagline centered
    if tagline:
        msg_y += 8
        tag_font = _get_font(font_family, max(14, int(base * 0.025)))
        tag_bbox = draw.textbbox((0, 0), tagline, font=tag_font)
        tw = tag_bbox[2] - tag_bbox[0]
        draw.text(((width - tw) // 2, msg_y), tagline, font=tag_font, fill=text_color + (150,))
        rendered.append(tagline)

    # Brand name at bottom, centered
    if brand_name:
        brand_font = _get_font(font_family, max(12, int(base * 0.02)))
        brand_text = brand_name.upper()
        bb = draw.textbbox((0, 0), brand_text, font=brand_font)
        bw = bb[2] - bb[0]
        draw.text(((width - bw) // 2, height - int(height * 0.06)), brand_text,
                  font=brand_font, fill=text_color + (120,))
        rendered.append(brand_text)

    return canvas, rendered


def render_bold_type(
    hero: Image.Image,
    width: int,
    height: int,
    message: str,
    tagline: Optional[str],
    brand_name: str,
    font_family: str,
    brand_colors: list[str],
    accent_color: Optional[str],
) -> tuple[Image.Image, list[str]]:
    """Bold typography: hero as tinted background, massive text overlay."""
    rendered = []

    canvas = _smart_resize(hero, width, height)

    # Heavy dark overlay for text contrast
    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    overlay_draw.rectangle([(0, 0), (width, height)], fill=(0, 0, 0, 160))
    canvas = Image.alpha_composite(canvas, overlay)

    # Add brand color tint
    if accent_color:
        tint_rgb = _hex_to_rgb(accent_color)
        tint = Image.new("RGBA", (width, height), tint_rgb + (25,))
        canvas = Image.alpha_composite(canvas, tint)

    draw = ImageDraw.Draw(canvas)
    base = min(width, height)
    padding = int(width * 0.08)

    # Oversized message
    msg_size = max(36, int(base * 0.09))
    msg_font = _get_cjk_font(msg_size) if _needs_cjk(message) else _get_font(font_family, msg_size)
    max_chars = max(10, int(width / (msg_size * 0.6)))
    lines = textwrap.wrap(message, width=max_chars)

    # Center vertically
    text_block = "\n".join(lines)
    block_bbox = draw.multiline_textbbox((0, 0), text_block, font=msg_font)
    block_h = block_bbox[3] - block_bbox[1]
    y_start = (height - block_h) // 2 - int(height * 0.05)

    for line in lines:
        draw.text((padding, y_start), line, font=msg_font, fill=(255, 255, 255, 255))
        line_bbox = draw.textbbox((0, 0), line, font=msg_font)
        y_start += (line_bbox[3] - line_bbox[1]) + 8

    rendered.append(message)

    # Accent underline below message
    if accent_color:
        line_y = y_start + 10
        accent_rgb = _hex_to_rgb(accent_color)
        draw.rectangle([(padding, line_y), (padding + int(width * 0.3), line_y + 4)],
                       fill=accent_rgb + (255,))

    # Tagline below
    if tagline:
        tag_y = y_start + 30
        tag_font = _get_font(font_family, max(16, int(base * 0.03)))
        draw.text((padding, tag_y), tagline, font=tag_font, fill=(255, 255, 255, 180))
        rendered.append(tagline)

    # Brand name in top-left
    if brand_name:
        brand_font = _get_font(font_family, max(14, int(base * 0.022)))
        brand_text = brand_name.upper()
        draw.text((padding, padding), brand_text, font=brand_font, fill=(255, 255, 255, 160))
        rendered.append(brand_text)

    return canvas, rendered


# ---------------------------------------------------------------------------
# Template registry
# ---------------------------------------------------------------------------

TEMPLATE_RENDERERS = {
    LayoutTemplate.PRODUCT_HERO: render_product_hero,
    LayoutTemplate.EDITORIAL: render_editorial,
    LayoutTemplate.SPLIT_PANEL: render_split_panel,
    LayoutTemplate.MINIMAL: render_minimal,
    LayoutTemplate.BOLD_TYPE: render_bold_type,
}


# ---------------------------------------------------------------------------
# Utility
# ---------------------------------------------------------------------------

def _smart_resize(img: Image.Image, tw: int, th: int) -> Image.Image:
    """Resize + center-crop to target dimensions."""
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)
    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return img.crop((left, top, left + tw, top + th))
