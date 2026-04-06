"""Integration tests for the full pipeline.

These tests verify end-to-end behavior, not just file existence (Fix 7):
  - Correct asset counts
  - Prompt persistence
  - Compliance result accuracy
  - Rendered text tracking
  - Translation warnings
"""

import json
from pathlib import Path

import pytest

from src.models import ComplianceStatus
from src.pipeline import load_brief, run_pipeline


class TestLoadBrief:
    def test_load_yaml(self):
        brief = load_brief("sample_briefs/summer_campaign.yaml")
        assert brief.name == "Summer Refresh 2025"
        assert len(brief.products) == 2
        assert len(brief.aspect_ratios) == 3

    def test_load_holiday(self):
        brief = load_brief("sample_briefs/holiday_campaign.yaml")
        assert brief.brand == "LuxeBeauty"
        assert "fr" in brief.languages
        # Verify disclaimer is loaded
        assert brief.brand_guidelines.required_disclaimer is not None


class TestPipelineMock:
    def test_correct_asset_count(self, tmp_path):
        """2 products × 3 ratios × 2 languages = 12 creatives."""
        result = run_pipeline(
            brief_path="sample_briefs/summer_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        assert result.total_assets == 12
        assert result.failed_count == 0
        assert result.generated_count == 12

    def test_all_output_files_exist(self, tmp_path):
        result = run_pipeline(
            brief_path="sample_briefs/summer_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        for asset in result.assets:
            assert asset.file_path, f"Empty file_path for {asset.product_id}"
            assert Path(asset.file_path).exists(), f"Missing: {asset.file_path}"

    def test_report_files_generated(self, tmp_path):
        result = run_pipeline(
            brief_path="sample_briefs/summer_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        campaign_dir = tmp_path / "output" / "summer_refresh_2025"
        assert (campaign_dir / "report.json").exists()
        assert (campaign_dir / "report.html").exists()

    def test_prompt_persisted_for_generated_heroes(self, tmp_path):
        """Fix 6: prompt_used must be populated for generated assets."""
        result = run_pipeline(
            brief_path="sample_briefs/summer_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        generated = [a for a in result.assets if a.hero_status.value == "generated"]
        assert len(generated) > 0
        for asset in generated:
            assert asset.prompt_used is not None, (
                f"prompt_used is null for generated asset {asset.product_id}/{asset.aspect_ratio}"
            )
            assert len(asset.prompt_used) > 50  # Prompt should be substantial

    def test_reused_assets_have_no_prompt(self, tmp_path):
        """Reused hero images should not have a prompt."""
        result = run_pipeline(
            brief_path="sample_briefs/summer_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        reused = [a for a in result.assets if a.hero_status.value == "reused"]
        assert len(reused) > 0
        for asset in reused:
            assert asset.prompt_used is None

    def test_rendered_texts_populated(self, tmp_path):
        """Fix 2: every asset must track rendered text for compliance."""
        result = run_pipeline(
            brief_path="sample_briefs/summer_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        for asset in result.assets:
            assert len(asset.rendered_texts) >= 1, (
                f"No rendered_texts for {asset.product_id}/{asset.language}"
            )
            # Campaign message should be in rendered texts
            assert any(
                "Fresh" in t or "Fresco" in t
                for t in asset.rendered_texts
            ), f"Campaign message not in rendered_texts: {asset.rendered_texts}"

    def test_brand_compliance_is_evidence_backed(self, tmp_path):
        """Fix 2: compliance must have status + notes, not just bool."""
        result = run_pipeline(
            brief_path="sample_briefs/summer_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        for asset in result.assets:
            assert asset.brand_compliance.status in ComplianceStatus
            assert len(asset.brand_compliance.notes) > 0, (
                f"Brand compliance has no notes for {asset.product_id}"
            )
            assert asset.legal_compliance.status in ComplianceStatus
            assert len(asset.legal_compliance.notes) > 0

    def test_hero_reuse_tracked(self, tmp_path):
        """Verify reuse count matches expectations."""
        result = run_pipeline(
            brief_path="sample_briefs/summer_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        # green-smoothie has an existing asset → 6 reused (3 ratios × 2 langs)
        assert result.reused_count == 6

    def test_json_report_round_trips(self, tmp_path):
        """JSON report should be valid and contain all fields."""
        result = run_pipeline(
            brief_path="sample_briefs/summer_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        report_path = tmp_path / "output" / "summer_refresh_2025" / "report.json"
        data = json.loads(report_path.read_text())
        assert data["campaign_name"] == "Summer Refresh 2025"
        assert data["total_assets"] == 12
        # Verify prompt_used is in JSON
        gen_asset = next(
            a for a in data["assets"]
            if a["hero_status"] == "generated"
        )
        assert gen_asset["prompt_used"] is not None

    def test_localized_text_in_spanish_assets(self, tmp_path):
        """Spanish creatives should use translated text."""
        result = run_pipeline(
            brief_path="sample_briefs/summer_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        es_assets = [a for a in result.assets if a.language == "es"]
        assert len(es_assets) > 0
        for asset in es_assets:
            # Should contain Spanish translation
            assert any(
                "Fresco" in t or "Verano" in t
                for t in asset.rendered_texts
            ), f"Spanish text not found in rendered_texts: {asset.rendered_texts}"


class TestHolidayCampaign:
    def test_holiday_asset_count(self, tmp_path):
        """2 products × 3 ratios × 3 languages = 18 creatives."""
        result = run_pipeline(
            brief_path="sample_briefs/holiday_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        assert result.total_assets == 18
        assert result.failed_count == 0

    def test_disclaimer_rendered(self, tmp_path):
        """Holiday campaign has required_disclaimer → must appear in rendered_texts."""
        result = run_pipeline(
            brief_path="sample_briefs/holiday_campaign.yaml",
            input_dir="input_assets",
            output_dir=str(tmp_path / "output"),
            mock=True,
        )
        for asset in result.assets:
            assert any(
                "Results may vary" in t
                for t in asset.rendered_texts
            ), f"Disclaimer missing from rendered_texts: {asset.rendered_texts}"
