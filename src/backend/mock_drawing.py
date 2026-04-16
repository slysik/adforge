"""Procedural image generation for the mock provider.

Produces deterministic product-style images using brand colors extracted
from the prompt, or a hash-derived palette as fallback.
"""

from __future__ import annotations

import hashlib
import math
import re
from colorsys import hsv_to_rgb

from PIL import Image, ImageDraw


def parse_brand_colors(prompt: str) -> list[tuple[int, int, int]]:
    """Extract hex colors from the 'Brand color palette:' clause in the prompt."""
    match = re.search(r"Brand color palette:\s*([^.]+)\.", prompt)
    if not match:
        return []
    hex_codes = re.findall(r"#([0-9A-Fa-f]{6})", match.group(1))
    return [(int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)) for h in hex_codes]


def procedural_image(product_name: str, w: int, h: int, prompt: str = "") -> Image.Image:
    """Generate a clean procedural product image using brand colors when available."""
    brand_rgbs = parse_brand_colors(prompt)

    digest = hashlib.md5(product_name.encode()).hexdigest()
    shape_variant = int(digest[4:6], 16)

    if len(brand_rgbs) >= 2:
        def lighten(rgb, factor=0.85):
            return tuple(int(c + (255 - c) * factor) for c in rgb)

        bg = lighten(brand_rgbs[0], 0.75)
        prod_color = brand_rgbs[1] if len(brand_rgbs) > 1 else brand_rgbs[0]
        accent = brand_rgbs[-1] if len(brand_rgbs) > 2 else brand_rgbs[0]
    else:
        hue = int(digest[:2], 16) / 255.0
        sat_seed = int(digest[2:4], 16) / 255.0
        r, g, b = hsv_to_rgb(hue, 0.15 + sat_seed * 0.15, 0.95)
        bg = (int(r * 255), int(g * 255), int(b * 255))
        r2, g2, b2 = hsv_to_rgb(hue, 0.4 + sat_seed * 0.3, 0.85)
        prod_color = (int(r2 * 255), int(g2 * 255), int(b2 * 255))
        r3, g3, b3 = hsv_to_rgb((hue + 0.5) % 1.0, 0.3, 0.9)
        accent = (int(r3 * 255), int(g3 * 255), int(b3 * 255))

    img = Image.new("RGBA", (w, h), bg + (255,))
    draw = ImageDraw.Draw(img)

    # Radial gradient
    cx, cy = w // 2, h // 2
    max_r = int(math.hypot(cx, cy))
    for radius in range(max_r, 0, -4):
        alpha = int(40 * (radius / max_r))
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=None,
            outline=(255, 255, 255, alpha),
            width=4,
        )

    # Central product shape
    shape_seed = shape_variant % 3
    margin_x = int(w * 0.28)
    margin_top = int(h * 0.18)
    margin_bot = int(h * 0.22)

    if shape_seed == 0:
        neck_w = int(w * 0.06)
        draw.rectangle(
            [cx - neck_w, margin_top, cx + neck_w, margin_top + int(h * 0.12)],
            fill=prod_color + (220,),
        )
        draw.rounded_rectangle(
            [margin_x, margin_top + int(h * 0.08), w - margin_x, h - margin_bot],
            radius=int(w * 0.04),
            fill=prod_color + (230,),
        )
        band_y = int(h * 0.42)
        draw.rectangle(
            [margin_x + 10, band_y, w - margin_x - 10, band_y + int(h * 0.08)],
            fill=accent + (120,),
        )
    elif shape_seed == 1:
        jar_r = int(min(w, h) * 0.25)
        draw.ellipse(
            [cx - jar_r, cy - jar_r, cx + jar_r, cy + jar_r],
            fill=prod_color + (230,),
        )
        draw.rectangle(
            [
                cx - int(jar_r * 0.7),
                cy - jar_r - int(h * 0.04),
                cx + int(jar_r * 0.7),
                cy - jar_r + int(h * 0.02),
            ],
            fill=accent + (180,),
        )
        draw.ellipse(
            [
                cx - int(jar_r * 0.5),
                cy - int(jar_r * 0.5),
                cx + int(jar_r * 0.2),
                cy + int(jar_r * 0.2),
            ],
            fill=(255, 255, 255, 40),
        )
    else:
        draw.rounded_rectangle(
            [margin_x, margin_top, w - margin_x, h - margin_bot],
            radius=int(w * 0.02),
            fill=prod_color + (230,),
        )
        panel_x = cx - int(w * 0.05)
        draw.line(
            [(panel_x, margin_top + 10), (panel_x, h - margin_bot - 10)],
            fill=accent + (100,),
            width=3,
        )
        draw.polygon(
            [
                (margin_x, margin_top),
                (cx, margin_top - int(h * 0.05)),
                (w - margin_x, margin_top),
            ],
            fill=prod_color + (200,),
        )

    # Accent circles
    for i in range(5):
        seed_val = int(digest[6 + i * 2 : 8 + i * 2], 16)
        ax = int((seed_val / 255) * w)
        ay = int((int(digest[8 + i * 2 : 10 + i * 2], 16) / 255) * h)
        ar = int(min(w, h) * 0.03 + (seed_val % 30))
        draw.ellipse([ax - ar, ay - ar, ax + ar, ay + ar], fill=accent + (50,))

    # Floor reflection
    reflection_h = int(h * 0.12)
    for y in range(reflection_h):
        alpha = int(30 * (1 - y / reflection_h))
        draw.line(
            [(0, h - reflection_h + y), (w, h - reflection_h + y)],
            fill=(255, 255, 255, alpha),
        )

    return img
