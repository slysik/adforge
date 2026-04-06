"""Tests for brand compliance and legal validation.

These tests verify that compliance checks produce accurate, evidence-backed
results — not just that they don't crash (Fix 7).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Optional

import pytest
from PIL import Image, ImageDraw

from src.models import ComplianceStatus
from src.validator import BrandComplianceChecker, LegalChecker


def _make_test_image(
    w: int = 200, h: int = 200,
    color: tuple = (128, 128, 128),
    path: str | None = None,
) -> Path:
    """Create a simple test image and return its path."""
    img = Image.new("RGB", (w, h), color)
    if path is None:
        tmp = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
        path = tmp.name
    img.save(path)
    return Path(path)


class TestBrandColorCheck:
    def test_detects_present_colors(self):
        """Brand color present in image → passed."""
        img_path = _make_test_image(color=(255, 0, 0))
        checker = BrandComplianceChecker(brand_colors=["#FF0000"])
        result = checker.check_brand_colors(img_path)
        assert result.status == ComplianceStatus.PASSED

    def test_detects_missing_colors(self):
        """Brand color absent from image → failed."""
        img_path = _make_test_image(color=(0, 0, 0))
        checker = BrandComplianceChecker(brand_colors=["#FF0000"])
        result = checker.check_brand_colors(img_path)
        assert result.status in (ComplianceStatus.FAILED, ComplianceStatus.WARNING)
        assert any("not detected" in n for n in result.notes)

    def test_no_colors_configured_skips(self):
        img_path = _make_test_image()
        checker = BrandComplianceChecker(brand_colors=[])
        result = checker.check_brand_colors(img_path)
        assert result.status == ComplianceStatus.NOT_CHECKED

    def test_partial_colors_is_warning(self):
        """Some brand colors present, some missing → warning (not failed)."""
        img_path = _make_test_image(color=(255, 0, 0))
        checker = BrandComplianceChecker(brand_colors=["#FF0000", "#0000FF"])
        result = checker.check_brand_colors(img_path)
        assert result.status == ComplianceStatus.WARNING


class TestLogoPresenceCheck:
    def test_no_logo_configured_skips(self):
        checker = BrandComplianceChecker(logo_path=None)
        result = checker.check_logo_presence(Path("dummy.jpg"))
        assert result.status == ComplianceStatus.NOT_CHECKED

    def test_missing_logo_file_fails(self):
        checker = BrandComplianceChecker(logo_path="/nonexistent/logo.png")
        result = checker.check_logo_presence(Path("dummy.jpg"))
        assert result.status == ComplianceStatus.FAILED
        assert any("not found" in n for n in result.notes)

    def test_logo_not_placed_fails(self):
        """Logo file exists but compositor didn't place it → failed."""
        # Use a real existing file path
        checker = BrandComplianceChecker(logo_path="input_assets/logo.png")
        result = checker.check_logo_presence(
            Path("dummy.jpg"), logo_was_placed=False,
        )
        assert result.status == ComplianceStatus.FAILED
        assert any("did not report" in n.lower() for n in result.notes)

    def test_logo_placed_with_pixel_check(self, tmp_path):
        """Logo placed → pixel verification on top-right region."""
        # Create an image with something in the top-right corner
        img = Image.new("RGBA", (400, 400), (200, 200, 200, 255))
        draw = ImageDraw.Draw(img)
        # Draw colored content in top-right (where logo goes)
        draw.ellipse([340, 10, 390, 60], fill=(255, 0, 0, 255))
        draw.rectangle([350, 15, 380, 55], fill=(0, 0, 255, 255))
        img_path = tmp_path / "test_logo.png"
        img.save(str(img_path))

        checker = BrandComplianceChecker(logo_path="input_assets/logo.png")
        result = checker.check_logo_presence(img_path, logo_was_placed=True)
        # Should pass or warn (not fail) since we placed content
        assert result.status in (ComplianceStatus.PASSED, ComplianceStatus.WARNING)


class TestTextCompliance:
    def test_prohibited_words_in_rendered_text(self):
        """Checks ALL rendered text, not just message."""
        checker = BrandComplianceChecker(prohibited_words=["cheap", "discount"])
        result = checker.check_text_compliance(
            ["Stay Fresh", "Now with cheap prices!", "BRAND"],
        )
        assert result.status == ComplianceStatus.FAILED
        assert any("cheap" in n for n in result.notes)

    def test_clean_text_passes(self):
        checker = BrandComplianceChecker(prohibited_words=["cheap"])
        result = checker.check_text_compliance(
            ["Premium quality", "Stay fresh", "BRAND"],
        )
        assert result.status == ComplianceStatus.PASSED

    def test_no_words_configured_skips(self):
        checker = BrandComplianceChecker(prohibited_words=[])
        result = checker.check_text_compliance(["anything"])
        assert result.status == ComplianceStatus.NOT_CHECKED

    def test_empty_rendered_texts_warns(self):
        checker = BrandComplianceChecker(prohibited_words=["bad"])
        result = checker.check_text_compliance([])
        assert result.status == ComplianceStatus.WARNING

    def test_checks_tagline_and_disclaimer(self):
        """Prohibited word in tagline or disclaimer should also be caught."""
        checker = BrandComplianceChecker(prohibited_words=["miracle"])
        result = checker.check_text_compliance(
            ["Buy this product", "Miracle results guaranteed!", "Terms apply"],
        )
        assert result.status == ComplianceStatus.FAILED


class TestFullBrandCheck:
    def test_aggregate_worst_status_wins(self, tmp_path):
        """Full check should return the worst individual status."""
        img_path = _make_test_image(path=str(tmp_path / "test.jpg"))
        checker = BrandComplianceChecker(
            brand_colors=["#FF0000"],  # Not in the gray image
            prohibited_words=[],
        )
        result = checker.full_check(
            img_path, rendered_texts=["Clean text"], logo_was_placed=False,
        )
        # Colors fail → should propagate to overall
        assert result.status in (ComplianceStatus.FAILED, ComplianceStatus.WARNING)


class TestLegalChecker:
    def test_flags_problematic_terms(self):
        checker = LegalChecker()
        result = checker.check(["This product is guaranteed to work!"])
        assert result.status == ComplianceStatus.WARNING
        assert any("guaranteed" in n for n in result.notes)

    def test_clean_text_passes(self):
        checker = LegalChecker()
        result = checker.check(["Stay fresh this summer"])
        assert result.status == ComplianceStatus.PASSED

    def test_custom_flags(self):
        checker = LegalChecker(extra_flags=["organic"])
        result = checker.check(["100% organic ingredients"])
        assert result.status == ComplianceStatus.WARNING

    def test_multiple_flags(self):
        checker = LegalChecker()
        result = checker.check(["Guaranteed miracle cure!"])
        assert result.status == ComplianceStatus.WARNING
        flagged = result.notes[0].lower()
        assert "guaranteed" in flagged
        assert "miracle" in flagged

    def test_checks_all_rendered_texts(self):
        """Legal check must inspect all rendered strings, not just first."""
        checker = LegalChecker()
        result = checker.check(["Clean message", "But guaranteed results"])
        assert result.status == ComplianceStatus.WARNING

    def test_empty_texts_not_checked(self):
        checker = LegalChecker()
        result = checker.check([])
        assert result.status == ComplianceStatus.NOT_CHECKED
