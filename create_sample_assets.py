"""
Generate sample input assets for testing:
  - A simple logo (FreshCo brand)
  - A clean green smoothie product photo (simulating a pre-existing asset)

These assets contain NO text labels or watermarks — they simulate real
product photography that would come from a DAM or photo shoot.
"""

from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path("input_assets")
ASSETS_DIR.mkdir(exist_ok=True)


def create_logo():
    """Create a simple FreshCo logo."""
    size = 400
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Circle background
    margin = 20
    draw.ellipse(
        [margin, margin, size - margin, size - margin],
        fill=(0, 168, 107, 255),  # #00A86B
    )

    # Inner circle
    inner = 50
    draw.ellipse(
        [inner, inner, size - inner, size - inner],
        fill=(255, 255, 255, 40),
    )

    # Text
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 72)
        font_sm = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 28)
    except (OSError, IOError):
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 72)
            font_sm = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28)
        except (OSError, IOError):
            font = ImageFont.load_default()
            font_sm = font

    # "FC" letters
    bbox = draw.textbbox((0, 0), "FC", font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(((size - tw) // 2, (size - th) // 2 - 20), "FC",
              fill=(255, 255, 255, 255), font=font)

    # "FreshCo" below
    bbox2 = draw.textbbox((0, 0), "FreshCo", font=font_sm)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(((size - tw2) // 2, (size + th) // 2 + 5), "FreshCo",
              fill=(255, 255, 255, 200), font=font_sm)

    path = ASSETS_DIR / "logo.png"
    img.save(str(path), "PNG")
    print(f"✓ Created logo: {path}")


def create_green_smoothie():
    """Create a clean green smoothie product image (no text labels)."""
    w, h = 1080, 1080
    # Rich green background simulating a product photo backdrop
    img = Image.new("RGB", (w, h), (34, 100, 50))
    draw = ImageDraw.Draw(img)

    # Radial gradient background
    cx, cy = w // 2, h // 2
    import math
    for radius in range(600, 0, -3):
        alpha = int(80 * (1 - radius / 600))
        r = 34 + alpha // 3
        g = 100 + alpha
        b = 50 + alpha // 4
        draw.ellipse(
            [cx - radius, cy - radius, cx + radius, cy + radius],
            fill=(r, min(g, 220), b),
        )

    # Glass body
    glass_left = w // 2 - 100
    glass_right = w // 2 + 100
    glass_top = h // 4 + 20
    glass_bottom = h * 3 // 4

    # Glass outline
    draw.rounded_rectangle(
        [glass_left, glass_top, glass_right, glass_bottom],
        radius=15,
        fill=(90, 185, 95),
        outline=(70, 155, 75),
        width=3,
    )

    # Smoothie fill gradient
    for y in range(glass_top + 30, glass_bottom - 5):
        t = (y - glass_top) / (glass_bottom - glass_top)
        g_val = int(175 - t * 30)
        draw.line(
            [(glass_left + 8, y), (glass_right - 8, y)],
            fill=(int(70 + t * 20), g_val, int(75 + t * 10)),
        )

    # Glass highlight
    draw.rectangle(
        [glass_left + 12, glass_top + 35, glass_left + 22, glass_bottom - 30],
        fill=(140, 220, 145),
    )

    # Straw
    straw_x = w // 2 + 25
    draw.line(
        [(straw_x, glass_top - 80), (straw_x + 12, glass_bottom - 80)],
        fill=(210, 210, 210),
        width=6,
    )

    # Decorative leaves (abstract nature elements)
    leaf_positions = [(180, 250, 70), (820, 350, 55), (220, 720, 60), (780, 680, 45)]
    for lx, ly, lsz in leaf_positions:
        draw.ellipse(
            [lx, ly, lx + lsz, ly + int(lsz * 1.8)],
            fill=(55, 145, 65),
        )
        draw.ellipse(
            [lx + 5, ly + 5, lx + lsz - 10, ly + int(lsz * 1.4)],
            fill=(65, 160, 70),
        )

    # Subtle floor reflection
    for y in range(h - 100, h):
        t = (y - (h - 100)) / 100
        draw.line([(0, y), (w, y)], fill=(25, int(80 - t * 30), int(40 - t * 15)))

    path = ASSETS_DIR / "green_smoothie.jpg"
    img.save(str(path), "JPEG", quality=90)
    print(f"✓ Created green smoothie asset: {path}")


if __name__ == "__main__":
    create_logo()
    create_green_smoothie()
    print("\n✅ Sample assets created in input_assets/")
