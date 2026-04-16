#!/usr/bin/env python3
"""Render a deterministic providers.py architecture slide as a PNG."""

from __future__ import annotations

from pathlib import Path
from textwrap import wrap

from PIL import Image, ImageDraw, ImageFont

WIDTH = 1920
HEIGHT = 1080
BG = "#fbfaf7"
TEXT = "#1a1a1a"
MUTED = "#575757"
LINE = "#1f1f1f"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/Library/Fonts/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _dashed_line(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], dash: int = 10, gap: int = 8, width: int = 4) -> None:
    x1, y1 = start
    x2, y2 = end
    if x1 == x2:
        step = dash + gap
        y = min(y1, y2)
        limit = max(y1, y2)
        while y < limit:
            draw.line((x1, y, x2, min(y + dash, limit)), fill=LINE, width=width)
            y += step
        return

    if y1 == y2:
        step = dash + gap
        x = min(x1, x2)
        limit = max(x1, x2)
        while x < limit:
            draw.line((x, y1, min(x + dash, limit), y2), fill=LINE, width=width)
            x += step


def _box(draw: ImageDraw.ImageDraw, xy: tuple[int, int, int, int], fill: str, title: str, lines: list[str], title_size: int = 38, body_size: int = 22) -> None:
    x1, y1, x2, y2 = xy
    draw.rounded_rectangle(xy, radius=26, fill=fill)
    inset = 8
    _dashed_line(draw, (x1 + 22, y1 + inset), (x2 - 22, y1 + inset))
    _dashed_line(draw, (x1 + 22, y2 - inset), (x2 - 22, y2 - inset))
    _dashed_line(draw, (x1 + inset, y1 + 22), (x1 + inset, y2 - 22))
    _dashed_line(draw, (x2 - inset, y1 + 22), (x2 - inset, y2 - 22))

    title_font = _font(title_size, bold=True)
    body_font = _font(body_size)
    tx = x1 + 26
    ty = y1 + 20
    draw.text((tx, ty), title, fill=TEXT, font=title_font)
    ty += title_size + 18
    for line in lines:
        for wrapped in wrap(line, width=max(20, int((x2 - x1) / 11))):
            draw.text((tx, ty), wrapped, fill=TEXT, font=body_font)
            ty += body_size + 8
        ty += 2


def _centered_label(draw: ImageDraw.ImageDraw, text: str, y: int, size: int = 34) -> None:
    font = _font(size, bold=True)
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((x, y), text, fill=TEXT, font=font)


def _arrow(draw: ImageDraw.ImageDraw, start: tuple[int, int], end: tuple[int, int], width: int = 5) -> None:
    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y2), fill=LINE, width=width)
    head = 14
    draw.polygon(
        [(x2, y2), (x2 - head, y2 - head // 2), (x2 - head, y2 + head // 2)],
        fill=LINE,
    )


def render(out_path: Path) -> None:
    img = Image.new("RGB", (WIDTH, HEIGHT), BG)
    draw = ImageDraw.Draw(img)

    title_font = _font(64, bold=True)
    subtitle_font = _font(28, bold=True)
    small_font = _font(22)

    draw.text((68, 30), "providers.py — Image Provider Abstraction", fill=TEXT, font=title_font)

    _box(
        draw,
        (600, 118, 1320, 196),
        "#f8d8cc",
        "pipeline.py initializes provider via get_provider()",
        [],
        title_size=28,
        body_size=20,
    )

    draw.text((605, 206), "Current runtime path: Gemini when configured, otherwise Mock.", fill=MUTED, font=subtitle_font)
    draw.text((905, 245), "Auto-Detect Chain", fill=TEXT, font=_font(34, bold=True))

    _box(
        draw,
        (65, 470, 545, 775),
        "#fff3c7",
        "ImageProvider ABC",
        [
            "generate(prompt, width, height, output_path,",
            "style_reference=None) -> (PIL.Image, GenerationMetadata)",
            "is_available() -> bool",
            "provider_type -> ProviderType",
            "model_name -> str",
        ],
        title_size=36,
        body_size=18,
    )

    _box(
        draw,
        (540, 300, 860, 535),
        "#f6cfc6",
        "FireflyProvider",
        [
            "Future option only",
            "Requires FIREFLY_CLIENT_ID +",
            "FIREFLY_CLIENT_SECRET",
            "Model: firefly-v3",
            "expand() available",
        ],
        title_size=34,
        body_size=18,
    )
    _box(
        draw,
        (900, 300, 1270, 535),
        "#d9e8f8",
        "GeminiProvider",
        [
            "Current path when",
            "GEMINI_API_KEY is present",
            "google-genai SDK",
            "Model: imagen-4.0",
            "API: imagen-4.0-generate-001",
        ],
        title_size=34,
        body_size=18,
    )
    _box(
        draw,
        (1310, 300, 1705, 535),
        "#ececec",
        "MockProvider",
        [
            "Always-available fallback",
            "Deterministic procedural images",
            "Can derive brand colors",
            "from prompt",
        ],
        title_size=34,
        body_size=18,
    )

    _arrow(draw, (860, 417), (900, 417))
    _arrow(draw, (1270, 417), (1310, 417))
    draw.text((615, 266), "If Firefly creds exist", fill=MUTED, font=small_font)
    draw.text((975, 266), "Else if Gemini key exists", fill=MUTED, font=small_font)
    draw.text((1410, 266), "Else fallback", fill=MUTED, font=small_font)

    _box(
        draw,
        (600, 585, 1265, 775),
        "#f8dfd3",
        "Explicit selection path",
        [
            "provider_type='firefly' | 'gemini' | 'dalle' -> selected provider",
            "Raises RuntimeError if that provider is unavailable",
            "mock=True or provider_type='mock' -> MockProvider",
        ],
        title_size=34,
        body_size=20,
    )

    _box(
        draw,
        (1310, 590, 1845, 825),
        "#dff1d5",
        "Retry Logic",
        [
            "_retry_api_call()",
            "Exponential backoff + jitter",
            "_is_transient_error() checks",
            "429 / 5xx / connection-style failures",
            "Default: max 3 retries, 30s max delay",
        ],
        title_size=36,
        body_size=20,
    )

    _box(
        draw,
        (1310, 845, 1725, 995),
        "#e7daf6",
        "DalleProvider",
        [
            "Explicit selection only",
            "Not in auto-detect chain",
            "Model: dall-e-3",
        ],
        title_size=34,
        body_size=20,
    )

    _box(
        draw,
        (250, 875, 1225, 1028),
        "#e5dbf3",
        "Pipeline hand-off",
        [
            "Providers save hero images to output_path and return GenerationMetadata.",
            "pipeline.py tracks hero file paths, then passes hero_path into compositor.py.",
        ],
        title_size=34,
        body_size=22,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")


if __name__ == "__main__":
    render(Path("data/slides/providers.png"))
