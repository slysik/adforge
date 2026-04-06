"""Tests for storage manager."""

import tempfile
from pathlib import Path

import pytest
from src.storage import StorageManager, slugify


class TestSlugify:
    def test_basic(self):
        assert slugify("Hello World") == "hello_world"

    def test_special_chars(self):
        assert slugify("Product A & B") == "product_a_and_b"

    def test_already_clean(self):
        assert slugify("clean-slug") == "clean-slug"


class TestStorageManager:
    def test_directories_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            sm = StorageManager(input_dir=Path(tmp) / "in", output_dir=Path(tmp) / "out")
            assert sm.input_dir.exists()
            assert sm.output_dir.exists()

    def test_campaign_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            sm = StorageManager(output_dir=Path(tmp) / "out")
            d = sm.get_campaign_dir("Summer Refresh 2025")
            assert d.exists()
            assert "summer_refresh_2025" in str(d)

    def test_creative_output_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            sm = StorageManager(output_dir=Path(tmp) / "out")
            p = sm.creative_output_path("Campaign", "product-1", "instagram_square", "en")
            assert "product-1" in str(p)
            assert "instagram_square" in str(p)
            assert p.name == "creative_en.jpg"

    def test_find_existing_hero_not_found(self):
        with tempfile.TemporaryDirectory() as tmp:
            sm = StorageManager(input_dir=Path(tmp) / "in")
            result = sm.find_existing_hero("nonexistent", None)
            assert result is None
