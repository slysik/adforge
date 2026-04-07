"""
Image composition module.

Takes hero images and composites them into final campaign creatives with:
  - Resizing / cropping to target aspect ratio
  - Campaign message text overlay with brand styling
  - Optional logo placement
  - Gradient overlays for text readability
  - Brand accent color usage
  - Required disclaimer rendering
"""

from __future__ import annotations

import textwrap
from pathlib import Path
from typing import Optional

from PIL import Image, ImageDraw, ImageFilter, ImageFont
from rich.console import Console

console = Console()


# ---------------------------------------------------------------------------
# Translation provider
# ---------------------------------------------------------------------------

class TranslationProvider:
    """
    Translates campaign text.

    Strategy:
      - Maintains a curated lookup of pre-approved translations for known
        campaign messages. This is intentional: ad copy requires human review,
        so machine translation is NOT used by default.
      - Unknown messages are returned in the source language with a warning
        flag, ensuring the pipeline never silently renders bad translations.
      - In production, this would integrate with a translation management
        system (TMS) like Smartling, Transifex, or a reviewed MT pipeline.
    """

    # Pre-approved translations (would come from a TMS in production)
    _APPROVED: dict[str, dict[str, str]] = {
        # Blue Beach House Designs campaigns
        "The perfect shell handbag for the season, complete with a lined interior, drawstring closure, and room for all your essentials.": {
            "es": "El bolso de conchas perfecto para la temporada, con interior forrado, cierre de cordón y espacio para todo lo esencial.",
            "fr": "Le sac à main coquillage parfait pour la saison, avec intérieur doublé, fermeture à cordon et de la place pour tous vos essentiels.",
            "de": "Die perfekte Muschel-Handtasche für die Saison, mit gefüttertem Inneren, Kordelzug und Platz für alles Wichtige.",
        },
        "Handcrafted Coastal Elegance": {
            "es": "Elegancia Costera Artesanal",
            "fr": "Élégance Côtière Artisanale",
            "de": "Handgefertigte Küsteneleganz",
        },
        "Bring the Coast Home This Summer": {
            "es": "Lleva la Costa a Tu Hogar Este Verano",
            "fr": "Ramenez la Côte Chez Vous Cet Été",
            "de": "Bringen Sie die Küste Diesen Sommer Nach Hause",
        },
        "Handcrafted Treasures from the Shore": {
            "es": "Tesoros Artesanales de la Costa",
            "fr": "Trésors Artisanaux du Rivage",
            "de": "Handgefertigte Schätze vom Strand",
        },
        "Gift the Coast This Holiday Season": {
            "es": "Regala la Costa Esta Temporada Navideña",
            "fr": "Offrez la Côte Pour les Fêtes",
            "de": "Verschenken Sie die Küste in Dieser Festzeit",
        },
        # Legacy campaigns
        "Stay Fresh This Summer": {
            "es": "Mantente Fresco Este Verano",
            "fr": "Restez Frais Cet Été",
            "de": "Bleib Frisch Diesen Sommer",
        },
        "Naturally Refreshing": {
            "es": "Naturalmente Refrescante",
            "fr": "Naturellement Rafraîchissant",
            "de": "Natürlich Erfrischend",
        },
        "New Year, New You": {
            "es": "Año Nuevo, Nuevo Tú",
            "fr": "Nouvelle Année, Nouveau Vous",
            "de": "Neues Jahr, Neues Du",
        },
        "Glow Into the New Year": {
            "es": "Brilla En El Año Nuevo",
            "fr": "Brillez Pour La Nouvelle Année",
            "de": "Strahle Ins Neue Jahr",
        },
    }

    def __init__(self):
        self._warnings: list[str] = []
        self._seen_warnings: set[tuple[str, str]] = set()

    @property
    def warnings(self) -> list[str]:
        return list(self._warnings)

    def clear_warnings(self):
        self._warnings.clear()
        self._seen_warnings.clear()

    def translate(self, text: str, language: str) -> tuple[str, bool]:
        """
        Translate text to target language.

        Returns (translated_text, was_translated).
        If was_translated is False, the original text is returned and a
        warning is recorded – the creative will show English copy, which is
        preferable to showing a bad machine translation on a live ad.
        """
        if language == "en":
            return text, True

        translated = self._APPROVED.get(text, {}).get(language)
        if translated:
            return translated, True

        # Dedupe: only warn once per (text, language) pair
        key = (text, language)
        if key not in self._seen_warnings:
            self._seen_warnings.add(key)
            self._warnings.append(
                f"No approved translation for '{text}' in '{language}' – "
                f"using source language. Submit to TMS for review."
            )
        return text, False


# Singleton for module-level access
_translator = TranslationProvider()


def get_translator() -> TranslationProvider:
    return _translator


# ---------------------------------------------------------------------------
# Font management
# ---------------------------------------------------------------------------

# Mapping of common font family names to OS-specific paths
_FONT_FAMILY_PATHS: dict[str, list[str]] = {
    "helvetica": [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
    ],
    "arial": [
        "/Library/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ],
    "georgia": [
        "/Library/Fonts/Georgia.ttf",
        "C:/Windows/Fonts/georgia.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ],
    "times": [
        "/Library/Fonts/Times New Roman.ttf",
        "C:/Windows/Fonts/times.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf",
    ],
}

_GENERIC_FALLBACKS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/SFNSDisplay.ttf",
    "/Library/Fonts/Arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "C:/Windows/Fonts/arial.ttf",
]

_CJK_FONT_PATHS = [
    "/System/Library/Fonts/PingFang.ttc",
    "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
    "/System/Library/Fonts/STHeiti Light.ttc",
    "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
    "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
]


def _get_font(font_family: str, size: int) -> ImageFont.FreeTypeFont:
    """Load a font matching the requested family, with graceful fallbacks."""
    # Try family-specific paths first
    family_key = font_family.lower().strip()
    paths = _FONT_FAMILY_PATHS.get(family_key, []) + _GENERIC_FALLBACKS

    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()


def _get_cjk_font(size: int) -> ImageFont.FreeTypeFont:
    """Get a font that supports CJK characters."""
    for p in _CJK_FONT_PATHS:
        try:
            return ImageFont.truetype(p, size)
        except (OSError, IOError):
            continue
    return _get_font("Arial", size)


def _needs_cjk(text: str) -> bool:
    """Check if text contains CJK characters."""
    for ch in text:
        if '\u4e00' <= ch <= '\u9fff' or '\u3040' <= ch <= '\u30ff' or '\uac00' <= ch <= '\ud7af':
            return True
    return False


# ---------------------------------------------------------------------------
# Color utilities
# ---------------------------------------------------------------------------

def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _draw_gradient_overlay(
    img: Image.Image, position: str = "bottom", opacity: int = 180
) -> Image.Image:
    """Draw a gradient overlay to improve text readability."""
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size

    if position == "bottom":
        gradient_height = int(h * 0.45)
        for y in range(gradient_height):
            alpha = int(opacity * (y / gradient_height))
            draw.line([(0, h - gradient_height + y), (w, h - gradient_height + y)],
                      fill=(0, 0, 0, alpha))
    elif position == "top":
        gradient_height = int(h * 0.35)
        for y in range(gradient_height):
            alpha = int(opacity * (1 - y / gradient_height))
            draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

    return Image.alpha_composite(img, overlay)


def _draw_text_with_shadow(
    draw: ImageDraw.Draw,
    position: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int, int],
    shadow_offset: int = 3,
) -> None:
    """Draw text with a drop shadow for better readability."""
    x, y = position
    draw.text((x + shadow_offset, y + shadow_offset), text,
              font=font, fill=(0, 0, 0, 160))
    draw.text((x, y), text, font=font, fill=fill)


# ---------------------------------------------------------------------------
# Compositor
# ---------------------------------------------------------------------------

class Compositor:
    """Composites hero images into final ad creatives."""

    def __init__(
        self,
        brand_colors: list[str] | None = None,
        accent_color: str | None = None,
        font_family: str = "Arial",
        logo_path: str | None = None,
        required_disclaimer: str | None = None,
    ):
        self.brand_colors = brand_colors or ["#000000", "#FFFFFF"]
        self.accent_color = accent_color
        self.font_family = font_family
        self.required_disclaimer = required_disclaimer
        self.logo: Image.Image | None = None
        self.logo_placed = False  # Track whether logo was actually placed

        if logo_path and Path(logo_path).exists():
            self.logo = Image.open(logo_path).convert("RGBA")

    def compose(
        self,
        hero_path: Path,
        output_path: Path,
        width: int,
        height: int,
        campaign_message: str,
        tagline: str | None = None,
        brand_name: str = "",
        language: str = "en",
        product_name: str = "",
        template: object = None,
    ) -> tuple[Path, list[str]]:
        """
        Produce a final campaign creative from a hero image.

        Returns (output_path, rendered_texts) where rendered_texts is
        a list of every text string actually rendered on the creative.

        If template is provided (a LayoutTemplate enum), uses the template
        renderer. Otherwise falls back to the default PRODUCT_HERO layout.
        """
        self.logo_placed = False
        rendered_texts: list[str] = []
        translator = get_translator()

        hero = Image.open(str(hero_path)).convert("RGBA")

        # --- Translate text ---
        message_translated, _ = translator.translate(campaign_message, language)
        tagline_translated = None
        if tagline:
            tagline_translated, _ = translator.translate(tagline, language)

        # --- Use template renderer if available ---
        if template is not None:
            try:
                from .templates import TEMPLATE_RENDERERS
                renderer = TEMPLATE_RENDERERS.get(template)
                if renderer:
                    canvas, texts = renderer(
                        hero=hero,
                        width=width,
                        height=height,
                        message=message_translated,
                        tagline=tagline_translated,
                        brand_name=brand_name,
                        font_family=self.font_family,
                        brand_colors=self.brand_colors,
                        accent_color=self.accent_color,
                    )
                    rendered_texts.extend(texts)
                else:
                    # Unknown template, fall through to default
                    template = None
            except ImportError:
                template = None

        if template is None:
            # --- Default PRODUCT_HERO layout ---
            canvas = self._smart_resize(hero, width, height)
            canvas = _draw_gradient_overlay(canvas, "bottom", opacity=190)

            canvas, texts = self._draw_campaign_text(
                canvas, message_translated, tagline_translated,
                brand_name, language, width, height,
            )
            rendered_texts.extend(texts)

        # --- Required disclaimer ---
        if self.required_disclaimer:
            canvas = self._draw_disclaimer(canvas, self.required_disclaimer, width, height)
            rendered_texts.append(self.required_disclaimer)

        # --- Logo ---
        if self.logo:
            canvas = self._place_logo(canvas, width, height)

        # --- Brand color accent bar (uses accent_color if available) ---
        canvas = self._draw_accent(canvas, width, height)

        # --- Save ---
        output_path.parent.mkdir(parents=True, exist_ok=True)
        canvas.convert("RGB").save(str(output_path), "JPEG", quality=95)
        return output_path, rendered_texts

    # ------------------------------------------------------------------
    def _smart_resize(self, img: Image.Image, tw: int, th: int) -> Image.Image:
        """Resize + center-crop to target dimensions preserving aspect ratio."""
        iw, ih = img.size
        scale = max(tw / iw, th / ih)
        new_w = int(iw * scale)
        new_h = int(ih * scale)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        left = (new_w - tw) // 2
        top = (new_h - th) // 2
        return img.crop((left, top, left + tw, top + th))

    # ------------------------------------------------------------------
    def _draw_campaign_text(
        self,
        canvas: Image.Image,
        message: str,
        tagline: str | None,
        brand_name: str,
        language: str,
        width: int,
        height: int,
    ) -> tuple[Image.Image, list[str]]:
        """Draw campaign text and return (canvas, list_of_rendered_strings)."""
        rendered: list[str] = []
        draw = ImageDraw.Draw(canvas)

        # Adaptive font sizes
        base = min(width, height)
        msg_size = max(28, int(base * 0.065))
        tag_size = max(18, int(base * 0.035))
        brand_size = max(16, int(base * 0.028))

        is_cjk = _needs_cjk(message)
        msg_font = _get_cjk_font(msg_size) if is_cjk else _get_font(self.font_family, msg_size)
        tag_font = _get_cjk_font(tag_size) if is_cjk else _get_font(self.font_family, tag_size)
        brand_font = _get_font(self.font_family, brand_size)

        # Wrap message
        max_chars = max(15, int(width / (msg_size * 0.55)))
        lines = textwrap.wrap(message, width=max_chars)

        padding = int(width * 0.06)
        y_cursor = height - padding

        # Brand name (top area)
        if brand_name:
            brand_text = brand_name.upper()
            _draw_text_with_shadow(draw, (padding, padding), brand_text,
                                   brand_font, (255, 255, 255, 220), shadow_offset=2)
            rendered.append(brand_text)

        # Tagline
        if tagline:
            tag_bbox = draw.textbbox((0, 0), tagline, font=tag_font)
            tag_h = tag_bbox[3] - tag_bbox[1]
            y_cursor -= tag_h + 10
            _draw_text_with_shadow(draw, (padding, y_cursor), tagline,
                                   tag_font, (255, 255, 255, 200), shadow_offset=2)
            rendered.append(tagline)

        # Main message
        text_block = "\n".join(lines)
        msg_bbox = draw.multiline_textbbox((0, 0), text_block, font=msg_font)
        msg_h = msg_bbox[3] - msg_bbox[1]
        y_cursor -= msg_h + 15

        for line in lines:
            _draw_text_with_shadow(draw, (padding, y_cursor), line,
                                   msg_font, (255, 255, 255, 255), shadow_offset=3)
            line_bbox = draw.textbbox((0, 0), line, font=msg_font)
            y_cursor += (line_bbox[3] - line_bbox[1]) + 8

        rendered.append(message)

        return canvas, rendered

    # ------------------------------------------------------------------
    def _draw_disclaimer(
        self, canvas: Image.Image, disclaimer: str, width: int, height: int,
    ) -> Image.Image:
        """Render required legal disclaimer text in small print near bottom."""
        draw = ImageDraw.Draw(canvas)
        disc_size = max(10, int(min(width, height) * 0.014))
        disc_font = _get_font(self.font_family, disc_size)
        padding = int(width * 0.06)

        # Position just above the accent bar
        bar_height = max(4, int(height * 0.006))
        y = height - bar_height - disc_size - 8

        draw.text((padding, y), disclaimer, font=disc_font, fill=(200, 200, 200, 180))
        return canvas

    # ------------------------------------------------------------------
    def _place_logo(self, canvas: Image.Image, width: int, height: int) -> Image.Image:
        """Place logo in top-right corner. Sets self.logo_placed on success."""
        if not self.logo:
            return canvas

        logo_max = int(min(width, height) * 0.12)
        logo = self.logo.copy()
        logo.thumbnail((logo_max, logo_max), Image.LANCZOS)

        padding = int(width * 0.04)
        x = width - logo.width - padding
        y = padding
        canvas.paste(logo, (x, y), logo)
        self.logo_placed = True
        return canvas

    # ------------------------------------------------------------------
    def _draw_accent(self, canvas: Image.Image, width: int, height: int) -> Image.Image:
        """Draw a brand-color accent bar at the bottom.

        Uses accent_color if configured, otherwise falls back to
        primary_colors[0].
        """
        overlay = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)
        bar_height = max(4, int(height * 0.006))

        # Prefer accent_color, fall back to primary
        if self.accent_color:
            color = _hex_to_rgb(self.accent_color)
        elif self.brand_colors:
            color = _hex_to_rgb(self.brand_colors[0])
        else:
            color = (0, 0, 0)

        draw.rectangle([(0, height - bar_height), (width, height)],
                       fill=color + (230,))
        return Image.alpha_composite(canvas, overlay)
