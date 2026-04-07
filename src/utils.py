"""
Shared utility functions for creative automation.

Enforces DRY (Don't Repeat Yourself) by centralizing common functions
used across multiple modules. This includes color conversion, image
resizing, and color analysis utilities.
"""

from __future__ import annotations

from PIL import Image


def hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """
    Convert a hex color string to an RGB tuple.

    Args:
        hex_color: A hex color string, with or without leading '#'.
                  Example: "#FF5733" or "FF5733"

    Returns:
        A tuple of (red, green, blue) values, each 0-255.

    Example:
        >>> hex_to_rgb("#FF5733")
        (255, 87, 51)
    """
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def smart_resize(img: Image.Image, tw: int, th: int) -> Image.Image:
    """
    Resize and center-crop an image to target dimensions.

    Preserves aspect ratio by scaling to the larger of the two required
    scales, then center-crops to the exact target dimensions. Uses
    high-quality LANCZOS resampling.

    Args:
        img: A PIL Image to resize.
        tw: Target width in pixels.
        th: Target height in pixels.

    Returns:
        A new Image with dimensions (tw, th).

    Example:
        >>> from PIL import Image
        >>> img = Image.new("RGB", (800, 600))
        >>> resized = smart_resize(img, 400, 300)
        >>> resized.size
        (400, 300)
    """
    iw, ih = img.size
    scale = max(tw / iw, th / ih)
    new_w = int(iw * scale)
    new_h = int(ih * scale)
    img = img.resize((new_w, new_h), Image.LANCZOS)

    left = (new_w - tw) // 2
    top = (new_h - th) // 2
    return img.crop((left, top, left + tw, top + th))


def luminance(rgb: tuple[int, int, int]) -> float:
    """
    Compute the relative luminance of an RGB color.

    Uses the standard relative luminance formula (WCAG 2.0):
    L = 0.2126 * R + 0.7152 * G + 0.0722 * B
    where R, G, B are normalized to 0.0-1.0.

    Args:
        rgb: A tuple of (red, green, blue) values, each 0-255.

    Returns:
        A float from 0.0 (black) to 1.0 (white).

    Example:
        >>> luminance((255, 255, 255))  # white
        1.0
        >>> luminance((0, 0, 0))  # black
        0.0
        >>> luminance((127, 127, 127))  # mid-gray
        0.21...
    """
    r, g, b = [c / 255.0 for c in rgb]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b
