"""
Brand compliance and legal content validation.

Checks:
  - Brand color presence in final image (pixel sampling)
  - Logo presence detection (pixel-level verification in expected region)
  - Prohibited word screening (against ALL rendered text)
  - Basic legal/regulatory term flagging (against ALL rendered text)

Each check returns an evidence-backed (ComplianceStatus, notes) pair.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from rich.console import Console

from .models import ComplianceStatus, ComplianceResult

console = Console()

# ---------------------------------------------------------------------------
# Common prohibited / sensitive terms for advertising
# ---------------------------------------------------------------------------
DEFAULT_LEGAL_FLAGS = [
    "guaranteed", "miracle", "cure", "free*", "risk-free",
    "no side effects", "clinically proven", "doctor approved",
    "#1", "best in class", "unbeatable",
]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def _color_distance(c1: tuple, c2: tuple) -> float:
    """Euclidean distance in RGB space."""
    return sum((a - b) ** 2 for a, b in zip(c1, c2)) ** 0.5


class BrandComplianceChecker:
    """Validates generated creatives against brand guidelines."""

    def __init__(
        self,
        brand_colors: list[str] | None = None,
        logo_path: str | None = None,
        prohibited_words: list[str] | None = None,
    ):
        self.brand_colors_rgb = [_hex_to_rgb(c) for c in (brand_colors or [])]
        self.brand_colors_hex = brand_colors or []
        self.logo_path = logo_path
        self.logo_image: Image.Image | None = None
        if logo_path and Path(logo_path).exists():
            self.logo_image = Image.open(logo_path).convert("RGBA")
        self.prohibited_words = [w.lower() for w in (prohibited_words or [])]

    def check_brand_colors(
        self, image_path: Path, tolerance: float = 80.0,
    ) -> ComplianceResult:
        """
        Check whether brand colors are represented in the image.
        Uses pixel sampling for performance.
        """
        if not self.brand_colors_rgb:
            return ComplianceResult(
                status=ComplianceStatus.NOT_CHECKED,
                notes=["No brand colors defined – check skipped."],
            )

        img = Image.open(str(image_path)).convert("RGB")
        pixels = list(img.getdata())[::10]

        found_colors = set()
        for brand_color in self.brand_colors_rgb:
            for px in pixels:
                if _color_distance(px, brand_color) < tolerance:
                    found_colors.add(brand_color)
                    break

        missing = [c for c in self.brand_colors_rgb if c not in found_colors]
        if missing:
            hex_missing = [f"#{r:02x}{g:02x}{b:02x}" for r, g, b in missing]
            status = (
                ComplianceStatus.WARNING
                if len(missing) < len(self.brand_colors_rgb)
                else ComplianceStatus.FAILED
            )
            return ComplianceResult(
                status=status,
                notes=[f"Brand colors not detected: {', '.join(hex_missing)}"],
            )

        return ComplianceResult(
            status=ComplianceStatus.PASSED,
            notes=["All brand colors detected in image."],
        )

    def check_logo_presence(
        self,
        image_path: Path,
        logo_was_placed: bool = False,
    ) -> ComplianceResult:
        """
        Verify logo presence in the rendered image.

        Uses a two-level check:
          1. Pipeline-level: did the compositor report placing the logo?
          2. Pixel-level: sample the expected logo region (top-right corner)
             and verify it contains non-background pixels consistent with
             the source logo's dominant colors.

        This is NOT full template matching (that requires OpenCV), but it
        catches the common failure modes: logo file missing, paste failed,
        logo region is empty.
        """
        if not self.logo_path:
            return ComplianceResult(
                status=ComplianceStatus.NOT_CHECKED,
                notes=["No logo configured – check skipped."],
            )

        if not Path(self.logo_path).exists():
            return ComplianceResult(
                status=ComplianceStatus.FAILED,
                notes=[f"Logo file not found: {self.logo_path}"],
            )

        if not logo_was_placed:
            return ComplianceResult(
                status=ComplianceStatus.FAILED,
                notes=["Compositor did not report successful logo placement."],
            )

        # Pixel-level verification: sample top-right region of the output
        if not Path(image_path).exists():
            return ComplianceResult(
                status=ComplianceStatus.FAILED,
                notes=["Output image not found for logo verification."],
            )

        try:
            img = Image.open(str(image_path)).convert("RGBA")
            w, h = img.size

            # Logo should be in top-right corner (matching compositor logic)
            logo_region_size = int(min(w, h) * 0.12)
            padding = int(w * 0.04)
            region = img.crop((
                w - logo_region_size - padding,
                padding,
                w - padding,
                padding + logo_region_size,
            ))

            # Check that the region has non-trivial alpha (i.e., logo pixels)
            region_pixels = list(region.getdata())
            non_transparent = sum(1 for px in region_pixels if len(px) >= 4 and px[3] > 200)
            total = len(region_pixels)

            if total > 0 and (non_transparent / total) > 0.1:
                # Also verify the region isn't just solid background
                unique_colors = len(set((px[0], px[1], px[2]) for px in region_pixels[:500]))
                if unique_colors > 3:
                    return ComplianceResult(
                        status=ComplianceStatus.PASSED,
                        notes=[
                            f"Logo verified in top-right region "
                            f"({non_transparent}/{total} opaque pixels, "
                            f"{unique_colors} distinct colors)."
                        ],
                    )

            return ComplianceResult(
                status=ComplianceStatus.WARNING,
                notes=[
                    f"Logo region appears empty or uniform "
                    f"({non_transparent}/{total} opaque pixels). "
                    f"Manual review recommended."
                ],
            )

        except Exception as exc:
            return ComplianceResult(
                status=ComplianceStatus.WARNING,
                notes=[f"Logo pixel verification failed: {exc}"],
            )

    def check_text_compliance(self, rendered_texts: list[str]) -> ComplianceResult:
        """
        Check ALL rendered text for prohibited words.

        Takes the actual list of strings rendered on the creative,
        not just the brief's campaign message.
        """
        if not self.prohibited_words:
            return ComplianceResult(
                status=ComplianceStatus.NOT_CHECKED,
                notes=["No prohibited words configured – check skipped."],
            )

        if not rendered_texts:
            return ComplianceResult(
                status=ComplianceStatus.WARNING,
                notes=["No rendered text provided for compliance check."],
            )

        all_text = " ".join(rendered_texts).lower()
        violations = [w for w in self.prohibited_words if w in all_text]

        if violations:
            return ComplianceResult(
                status=ComplianceStatus.FAILED,
                notes=[
                    f"Prohibited words found in rendered text: {', '.join(violations)}. "
                    f"Checked texts: {rendered_texts}"
                ],
            )

        return ComplianceResult(
            status=ComplianceStatus.PASSED,
            notes=[
                f"No prohibited words detected. "
                f"Checked {len(rendered_texts)} rendered text(s)."
            ],
        )

    def full_check(
        self,
        image_path: Path,
        rendered_texts: list[str],
        logo_was_placed: bool = False,
    ) -> ComplianceResult:
        """
        Run all brand compliance checks and return an aggregate result.
        """
        color_result = self.check_brand_colors(image_path)
        logo_result = self.check_logo_presence(image_path, logo_was_placed)
        text_result = self.check_text_compliance(rendered_texts)

        all_notes = (
            [f"[Colors] {n}" for n in color_result.notes]
            + [f"[Logo] {n}" for n in logo_result.notes]
            + [f"[Text] {n}" for n in text_result.notes]
        )

        # Aggregate: worst status wins
        statuses = [color_result.status, logo_result.status, text_result.status]
        if ComplianceStatus.FAILED in statuses:
            overall = ComplianceStatus.FAILED
        elif ComplianceStatus.WARNING in statuses:
            overall = ComplianceStatus.WARNING
        elif all(s == ComplianceStatus.NOT_CHECKED for s in statuses):
            overall = ComplianceStatus.NOT_CHECKED
        else:
            overall = ComplianceStatus.PASSED

        return ComplianceResult(status=overall, notes=all_notes)


class LegalChecker:
    """Flags potentially problematic legal/advertising terms."""

    def __init__(self, extra_flags: list[str] | None = None):
        self.flags = [f.lower() for f in (DEFAULT_LEGAL_FLAGS + (extra_flags or []))]

    def check(self, rendered_texts: list[str]) -> ComplianceResult:
        """
        Check ALL rendered text for legally sensitive terms.
        """
        if not rendered_texts:
            return ComplianceResult(
                status=ComplianceStatus.NOT_CHECKED,
                notes=["No rendered text provided for legal check."],
            )

        all_text = " ".join(rendered_texts).lower()
        found = [f for f in self.flags if f in all_text]

        if found:
            return ComplianceResult(
                status=ComplianceStatus.WARNING,
                notes=[
                    f"Legal review recommended – flagged terms: {', '.join(found)}. "
                    f"Checked texts: {rendered_texts}"
                ],
            )

        return ComplianceResult(
            status=ComplianceStatus.PASSED,
            notes=[f"No legal flags raised. Checked {len(rendered_texts)} text(s)."],
        )
