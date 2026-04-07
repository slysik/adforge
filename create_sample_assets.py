"""
Generate fallback sample input assets for testing when real product
photos are not available.

Real assets (committed to input_assets/):
  - logo.png — Blue Beach House Designs logo
  - resort-shell-handbag.png — Resort shell handbag product photo
  - bespoke-rattan-cowrie-shell-box.png — Cowrie shell box product photo
  - painted-shell-art.png — Painted shell art product photo

This script creates placeholder versions only if the real files are missing,
plus a green_smoothie.jpg needed by legacy test briefs.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

ASSETS_DIR = Path("input_assets")
ASSETS_DIR.mkdir(exist_ok=True)


def create_logo():
    """Create a Blue Beach House Designs logo if one doesn't exist."""
    path = ASSETS_DIR / "logo.png"
    if path.exists():
        print(f"  ✓ Logo already exists: {path}")
        return

    size = 400
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Circle background — ocean blue
    margin = 20
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(27, 79, 114, 255),  # #1B4F72
    )

    # Inner ring
    inner = 50
    draw.ellipse(
        [inner, inner, size - inner, size - inner],
        fill=(27, 79, 114, 255),
        outline=(245, 230, 202, 100),
        width=3,
    )

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Georgia.ttf", 60)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Georgia.ttf", 22)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf", 60)
            font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf", 22)
        except (OSError, IOError):
            font = ImageFont.load_default()
            font_sm = font

    bbox = draw.textbbox((0, 0), "BB", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - 25), "BB",
              fill=(245, 230, 202, 255), font=font)

    label = "Blue Beach House"
    bbox2 = draw.textbbox((0, 0), label, font=font_sm)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((size - tw2) // 2, (size + th) // 2 - 5), label,
              fill=(245, 230, 202, 200), font=font_sm)

    img.save(str(path), "PNG")
    print(f"✓ Created logo: {path}")


def _create_placeholder(filename: str, label: str, bg_color: tuple):
    """Create a simple placeholder product image if the real one is missing."""
    path = ASSETS_DIR / filename
    if path.exists():
        print(f"  ✓ {label} already exists: {path}")
        return

    w, h = 1080, 1080
    img = Image.new("RGB", (w, h), bg_color)
    draw = ImageDraw.Draw(img)

    cx, cy = w // 2, h // 2
    for radius in range(500, 0, -5):
        alpha = int(40 * (1 - radius / 500))
        r = min(bg_color[0] + alpha, 255)
        g = min(bg_color[1] + alpha, 255)
        b = min(bg_color[2] + alpha, 255)
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius], fill=(r, g, b))

    try:
        font = ImageFont.truetype("/System/Library/Fonts/Georgia.ttf", 36)
    except (OSError, IOError):
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), label, font=font)
    tw = bbox[2] - bbox[0]
    draw.text(((w - tw) // 2, h - 120), label, fill=(255, 255, 255), font=font)

    ext = Path(filename).suffix.lower()
    if ext in (".jpg", ".jpeg"):
        img.save(str(path), "JPEG", quality=90)
    else:
        img.save(str(path), "PNG")
    print(f"✓ Created placeholder: {path}")


def create_green_smoothie():
    """Create a green smoothie placeholder (needed by legacy tests)."""
    _create_placeholder("green_smoothie.jpg", "Green Smoothie", (34, 100, 50))


if __name__ == "__main__":
    create_logo()
    _create_placeholder("resort-shell-handbag.png", "Resort Shell Handbag", (180, 150, 120))
    _create_placeholder("bespoke-rattan-cowrie-shell-box.png", "Cowrie Shell Box", (160, 140, 110))
    _create_placeholder("painted-shell-art.png", "Painted Shell Art", (200, 180, 160))
    create_green_smoothie()
    print("\n✅ Sample assets created in input_assets/")
