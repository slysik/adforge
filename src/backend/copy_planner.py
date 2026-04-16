"""
Planner for campaign headline copy.

Purpose:
  Generate a product-specific "WOW factor" headline by feeding the full user
  brief (brand voice, audience, region, theme, colors, typography, product
  description + keywords) plus the product photo into gemini-2.5-flash. The
  output replaces the static ``brief.message`` at composition time so each
  creative gets a headline tailored to its product.

Non-goals:
  - Does not touch hero imagery (product photos stay as-is).
  - Does not rewrite the tagline (optional follow-up).
  - Fails silent — on any planner error the caller falls back to brief.message.
"""

from __future__ import annotations

import mimetypes
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from rich.console import Console

from .models import CampaignBrief, Product
from .retry import retry_api_call

console = Console()


SYSTEM_INSTRUCTION = (
    "You are a senior advertising copywriter for a premium, handcrafted "
    "coastal lifestyle brand. Given a product photo and a full campaign brief, "
    "produce ONE punchy, WOW-factor headline tailored to THIS product:\n"
    "  - 4 to 10 words, sentence case (no ALL CAPS)\n"
    "  - emotionally evocative, specific to the product's material/form\n"
    "  - consistent with the brand voice (editorial, elegant, handcrafted)\n"
    "  - safe to overlay on the photo (no words that duplicate brand or tagline)\n"
    "  - must not use any prohibited words listed in the brief\n"
    "  - must not contain claims, superlatives like '#1', 'guaranteed', or 'miracle'\n"
    "Return ONLY the headline text. No quotes. No preamble. No trailing punctuation."
)

PLANNER_MODEL = "gemini-2.5-flash"


@dataclass
class CopyPlanResult:
    headline: str
    model: str
    language: str


class CopyPlanner:
    """Generates WOW-factor headline copy per product + language.

    Uses gemini-2.5-flash with the product photo as multimodal context so the
    headline can reference what's actually in the image (texture, palette,
    silhouette), not just the brief's description.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (
            api_key or os.getenv("GEMINI_API_KEY") or os.getenv("NANO_BANANA_API_KEY")
        )
        self._client = None
        if self.api_key:
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                console.print(
                    "[yellow]⚠ google-genai not installed — copy planner disabled.[/yellow]"
                )
            except Exception as exc:
                console.print(
                    f"[yellow]⚠ Copy planner init failed ({exc}) — disabled.[/yellow]"
                )

    def is_available(self) -> bool:
        return self._client is not None

    def plan_headline(
        self,
        brief: CampaignBrief,
        product: Product,
        product_photo: Optional[Path],
        language: str = "en",
    ) -> Optional[CopyPlanResult]:
        """Generate a headline or return None on any failure."""
        if not self._client:
            return None

        from google.genai import types

        brief_summary = self._format_brief(brief, product, language)
        contents: list = [brief_summary]

        if product_photo and product_photo.exists():
            mime, _ = mimetypes.guess_type(str(product_photo))
            if not mime or not mime.startswith("image/"):
                mime = "image/png"
            try:
                contents.append(
                    types.Part.from_bytes(
                        data=product_photo.read_bytes(), mime_type=mime
                    )
                )
            except OSError as exc:
                console.print(
                    f"[yellow]⚠ Copy planner could not read {product_photo}: {exc}[/yellow]"
                )

        def call():
            return self._client.models.generate_content(
                model=PLANNER_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_INSTRUCTION,
                    temperature=0.9,
                    max_output_tokens=200,
                ),
            )

        try:
            response = retry_api_call(call)
            headline = (getattr(response, "text", "") or "").strip().strip('"\'')
        except Exception as exc:
            console.print(
                f"[yellow]⚠ Copy planner failed for {product.id} ({exc})[/yellow]"
            )
            return None

        if not headline:
            console.print(
                f"[yellow]⚠ Copy planner returned empty headline for {product.id}[/yellow]"
            )
            return None

        # Headlines look cleaner without trailing punctuation.
        headline = headline.rstrip(".,;:!?–—- ")

        return CopyPlanResult(
            headline=headline, model=PLANNER_MODEL, language=language
        )

    @staticmethod
    def _format_brief(
        brief: CampaignBrief, product: Product, language: str
    ) -> str:
        bg = brief.brand_guidelines
        colors = ", ".join(bg.primary_colors)
        prohibited = ", ".join(bg.prohibited_words) or "(none)"
        keywords = ", ".join(product.keywords) or "(none)"
        return (
            "CAMPAIGN BRIEF\n"
            f"Brand: {brief.brand}\n"
            f"Campaign name: {brief.name}\n"
            f"Primary message (for reference, do not repeat verbatim): {brief.message}\n"
            f"Existing tagline: {brief.tagline or '(none)'}\n"
            f"Theme: {brief.theme or '(none)'}\n"
            f"Target region: {brief.target_region}\n"
            f"Target audience: {brief.target_audience}\n"
            f"Brand palette: {colors}\n"
            f"Accent color: {bg.accent_color or '(none)'}\n"
            f"Font family: {bg.font_family}\n"
            f"Prohibited words: {prohibited}\n"
            f"Output language: {language}\n\n"
            "PRODUCT\n"
            f"Name: {product.name}\n"
            f"ID: {product.id}\n"
            f"Description: {product.description}\n"
            f"Keywords: {keywords}\n\n"
            "The attached image is the exact product photo that will sit behind "
            "the headline. Use it as a style/subject cue."
        )
