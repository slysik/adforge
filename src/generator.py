"""
GenAI image generation module.

Supports:
  - OpenAI DALL-E 3 (primary)
  - Mock mode: generates clean, label-free product-style images for testing
"""

from __future__ import annotations

import hashlib
import io
import math
import os
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFilter
from rich.console import Console

console = Console()

# ---------------------------------------------------------------------------
# Size mapping – DALL-E 3 only supports specific sizes
# ---------------------------------------------------------------------------
DALLE3_SIZES = {
    "1:1": "1024x1024",
    "9:16": "1024x1792",
    "16:9": "1792x1024",
}

# Canonical dimensions for mock mode per aspect ratio
MOCK_DIMS = {
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


def _build_prompt(
    product_name: str,
    product_description: str,
    keywords: list[str],
    campaign_message: str,
    target_audience: str,
    target_region: str,
    brand_name: str,
) -> str:
    """Construct a rich, descriptive prompt for hero image generation."""
    kw = ", ".join(keywords) if keywords else ""
    return (
        f"A high-quality, professional advertising photograph for a social media campaign. "
        f"Product: {product_name} – {product_description}. "
        f"Brand: {brand_name}. "
        f"Campaign theme: {campaign_message}. "
        f"Target audience: {target_audience} in {target_region}. "
        f"Visual keywords: {kw}. "
        f"The image should be vibrant, eye-catching, product-centric, clean background, "
        f"studio lighting, modern and aspirational lifestyle feel. "
        f"Do NOT include any text, watermarks, logos, or words in the image."
    )


class ImageGenerator:
    """Generates hero images via GenAI or mock mode."""

    def __init__(self, api_key: Optional[str] = None, mock: bool = False):
        self.mock = mock
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key and not self.mock:
            console.print(
                "[yellow]⚠ No OPENAI_API_KEY found – falling back to mock mode.[/yellow]"
            )
            self.mock = True

        self._client = None
        if not self.mock:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except Exception as exc:
                console.print(f"[yellow]⚠ OpenAI init failed ({exc}); using mock mode.[/yellow]")
                self.mock = True

    # ------------------------------------------------------------------
    def generate_hero(
        self,
        product_name: str,
        product_description: str,
        keywords: list[str],
        campaign_message: str,
        target_audience: str,
        target_region: str,
        brand_name: str,
        aspect_ratio: str = "1:1",
        output_path: Optional[Path] = None,
    ) -> tuple[Path, str]:
        """
        Generate a hero image and return (file_path, prompt_used).
        The hero image is a clean product photo with NO text or labels.
        """
        prompt = _build_prompt(
            product_name, product_description, keywords,
            campaign_message, target_audience, target_region, brand_name,
        )

        if self.mock:
            img = self._mock_generate(product_name, keywords, aspect_ratio)
        else:
            img = self._dalle_generate(prompt, aspect_ratio)

        if output_path is None:
            output_path = Path(
                f"hero_{product_name.replace(' ', '_')}_{aspect_ratio.replace(':', 'x')}.png"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "PNG")
        return output_path, prompt

    # ------------------------------------------------------------------
    def _dalle_generate(self, prompt: str, aspect_ratio: str) -> Image.Image:
        """Call OpenAI DALL-E 3 API."""
        size = DALLE3_SIZES.get(aspect_ratio, "1024x1024")
        console.print(f"  [cyan]Calling DALL-E 3 ({size})…[/cyan]")

        response = self._client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            n=1,
            size=size,
            quality="standard",
        )

        image_url = response.data[0].url
        img_bytes = requests.get(image_url, timeout=120).content
        return Image.open(io.BytesIO(img_bytes)).convert("RGBA")

    # ------------------------------------------------------------------
    def _mock_generate(
        self,
        product_name: str,
        keywords: list[str],
        aspect_ratio: str,
    ) -> Image.Image:
        """
        Generate a clean, label-free product-style mock image.

        NO text labels, NO "[MOCK]" watermarks, NO aspect-ratio captions.
        This produces a plausible product hero image using procedural graphics:
          - Deterministic color palette derived from product name
          - Central product silhouette shape
          - Ambient lighting / radial gradient
          - Accent elements from keywords
        """
        w, h = MOCK_DIMS.get(aspect_ratio, (1080, 1080))

        # Deterministic palette from product name
        digest = hashlib.md5(product_name.encode()).hexdigest()
        hue = int(digest[:2], 16) / 255.0
        sat_seed = int(digest[2:4], 16) / 255.0

        from colorsys import hsv_to_rgb

        # Background: soft muted tone
        r, g, b = hsv_to_rgb(hue, 0.15 + sat_seed * 0.15, 0.95)
        bg = (int(r * 255), int(g * 255), int(b * 255))

        # Product color: richer version of same hue
        r2, g2, b2 = hsv_to_rgb(hue, 0.4 + sat_seed * 0.3, 0.85)
        prod_color = (int(r2 * 255), int(g2 * 255), int(b2 * 255))

        # Accent: complementary hue
        r3, g3, b3 = hsv_to_rgb((hue + 0.5) % 1.0, 0.3, 0.9)
        accent = (int(r3 * 255), int(g3 * 255), int(b3 * 255))

        img = Image.new("RGBA", (w, h), bg + (255,))
        draw = ImageDraw.Draw(img)

        # --- Radial gradient (soft studio lighting effect) ---
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

        # --- Central product shape (bottle/jar/box silhouette) ---
        shape_seed = int(digest[4:6], 16) % 3
        margin_x = int(w * 0.28)
        margin_top = int(h * 0.18)
        margin_bot = int(h * 0.22)

        if shape_seed == 0:
            # Bottle shape
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
            # Label band
            band_y = int(h * 0.42)
            draw.rectangle(
                [margin_x + 10, band_y, w - margin_x - 10, band_y + int(h * 0.08)],
                fill=accent + (120,),
            )
        elif shape_seed == 1:
            # Jar / circular shape
            jar_r = int(min(w, h) * 0.25)
            draw.ellipse(
                [cx - jar_r, cy - jar_r, cx + jar_r, cy + jar_r],
                fill=prod_color + (230,),
            )
            # Lid
            draw.rectangle(
                [cx - int(jar_r * 0.7), cy - jar_r - int(h * 0.04),
                 cx + int(jar_r * 0.7), cy - jar_r + int(h * 0.02)],
                fill=accent + (180,),
            )
            # Inner highlight
            draw.ellipse(
                [cx - int(jar_r * 0.5), cy - int(jar_r * 0.5),
                 cx + int(jar_r * 0.2), cy + int(jar_r * 0.2)],
                fill=(255, 255, 255, 40),
            )
        else:
            # Box / carton shape
            draw.rounded_rectangle(
                [margin_x, margin_top, w - margin_x, h - margin_bot],
                radius=int(w * 0.02),
                fill=prod_color + (230,),
            )
            # Panel line
            panel_x = cx - int(w * 0.05)
            draw.line(
                [(panel_x, margin_top + 10), (panel_x, h - margin_bot - 10)],
                fill=accent + (100,),
                width=3,
            )
            # Top flap illusion
            draw.polygon(
                [(margin_x, margin_top), (cx, margin_top - int(h * 0.05)),
                 (w - margin_x, margin_top)],
                fill=prod_color + (200,),
            )

        # --- Decorative accent circles (abstract product elements) ---
        for i in range(5):
            seed_val = int(digest[6 + i * 2: 8 + i * 2], 16)
            ax = int((seed_val / 255) * w)
            ay = int((int(digest[8 + i * 2: 10 + i * 2], 16) / 255) * h)
            ar = int(min(w, h) * 0.03 + (seed_val % 30))
            draw.ellipse(
                [ax - ar, ay - ar, ax + ar, ay + ar],
                fill=accent + (50,),
            )

        # --- Subtle reflection / floor gradient at bottom ---
        reflection_h = int(h * 0.12)
        for y in range(reflection_h):
            alpha = int(30 * (1 - y / reflection_h))
            draw.line(
                [(0, h - reflection_h + y), (w, h - reflection_h + y)],
                fill=(255, 255, 255, alpha),
            )

        return img
