"""Tests for the pipeline performance tracker."""

import time

import pytest

from src.tracker import PipelineTracker, AssetMetrics, StageMetrics


class TestPipelineTracker:
    def test_stage_tracking(self):
        tracker = PipelineTracker()
        with tracker.stage("test_stage") as stage:
            stage.items_processed = 5
            stage.api_calls = 2
            stage.estimated_cost_usd = 0.08
            time.sleep(0.01)

        metrics = tracker.finalize()
        assert len(metrics.stages) == 1
        assert metrics.stages[0].name == "test_stage"
        assert metrics.stages[0].items_processed == 5
        assert metrics.stages[0].api_calls == 2
        assert metrics.stages[0].elapsed_ms >= 10

    def test_multiple_stages(self):
        tracker = PipelineTracker()
        with tracker.stage("a") as s:
            s.api_calls = 1
            s.estimated_cost_usd = 0.04
        with tracker.stage("b") as s:
            s.api_calls = 2
            s.estimated_cost_usd = 0.08

        metrics = tracker.finalize()
        assert len(metrics.stages) == 2
        assert metrics.total_api_calls == 3
        assert abs(metrics.total_estimated_cost_usd - 0.12) < 0.001

    def test_asset_tracking(self):
        tracker = PipelineTracker()
        tracker.track_asset(AssetMetrics(
            product_id="prod-a",
            aspect_ratio="1:1",
            language="en",
            provider="mock",
            generation_ms=50,
            composition_ms=20,
            validation_ms=5,
        ))

        metrics = tracker.finalize()
        assert len(metrics.assets) == 1
        assert metrics.assets[0].product_id == "prod-a"

    def test_to_dict_serialization(self):
        tracker = PipelineTracker()
        with tracker.stage("test") as s:
            s.items_processed = 1
        tracker.track_asset(AssetMetrics(
            product_id="p", aspect_ratio="1:1", language="en",
        ))

        metrics = tracker.finalize()
        d = metrics.to_dict()
        assert "total_elapsed_ms" in d
        assert "stages" in d
        assert "per_asset" in d
        assert len(d["stages"]) == 1
        assert len(d["per_asset"]) == 1
