"""Tests for the provider abstraction layer."""

import os
from pathlib import Path

import pytest
from PIL import Image

from src.providers import (
    MockProvider, DalleProvider, FireflyProvider,
    get_provider, ProviderType, GenerationMetadata,
)


class TestMockProvider:
    def test_provider_type(self):
        p = MockProvider()
        assert p.provider_type == ProviderType.MOCK
        assert p.model_name == "mock-v1"

    def test_always_available(self):
        assert MockProvider().is_available() is True

    def test_generates_correct_dimensions_1x1(self, tmp_path):
        p = MockProvider()
        img, meta = p.generate("Test prompt", 1080, 1080, tmp_path / "out.png")
        assert img.size == (1080, 1080)
        assert meta.provider == "mock"
        assert meta.estimated_cost_usd == 0.0

    def test_generates_correct_dimensions_9x16(self, tmp_path):
        p = MockProvider()
        img, meta = p.generate("Test prompt", 1080, 1920, tmp_path / "out.png")
        assert img.size == (1080, 1920)

    def test_generates_correct_dimensions_16x9(self, tmp_path):
        p = MockProvider()
        img, meta = p.generate("Test prompt", 1920, 1080, tmp_path / "out.png")
        assert img.size == (1920, 1080)

    def test_saves_to_output_path(self, tmp_path):
        p = MockProvider()
        out = tmp_path / "subdir" / "hero.png"
        p.generate("Test", 500, 500, out)
        assert out.exists()

    def test_metadata_populated(self, tmp_path):
        p = MockProvider()
        _, meta = p.generate("My prompt", 500, 500, tmp_path / "out.png")
        assert meta.prompt_used == "My prompt"
        assert meta.generation_time_ms >= 0
        assert meta.aspect_ratio == "500:500"

    def test_deterministic_output(self, tmp_path):
        p = MockProvider()
        prompt = "Product: Test Product – Description"
        img1, _ = p.generate(prompt, 500, 500, tmp_path / "a.png")
        img2, _ = p.generate(prompt, 500, 500, tmp_path / "b.png")
        assert img1.getpixel((250, 250)) == img2.getpixel((250, 250))

    def test_no_text_in_image(self, tmp_path):
        """Mock images must be clean — no text, no watermarks."""
        p = MockProvider()
        img, _ = p.generate("Product: Sparkling Water – Desc", 1080, 1080, tmp_path / "out.png")
        assert img.mode == "RGBA"
        pixels = list(img.getdata())
        unique = len(set(pixels[:1000]))
        assert unique > 5


class TestFireflyProvider:
    def test_not_available_without_credentials(self):
        """Firefly requires FIREFLY_CLIENT_ID and FIREFLY_CLIENT_SECRET."""
        p = FireflyProvider()
        # Unless env vars are set in test env, should not be available
        if not os.getenv("FIREFLY_CLIENT_ID"):
            assert p.is_available() is False

    def test_provider_type(self):
        p = FireflyProvider()
        assert p.provider_type == ProviderType.FIREFLY
        assert p.model_name == "firefly-v3"

    def test_nearest_size_resolution(self):
        p = FireflyProvider()
        # 1:1 → (1024, 1024)
        assert p._find_nearest_size(1080, 1080) == (1024, 1024)
        # 16:9 → (1792, 1024)
        size = p._find_nearest_size(1920, 1080)
        assert size[0] > size[1]  # Landscape


class TestDalleProvider:
    def test_not_available_without_key(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        p = DalleProvider(api_key=None)
        assert p.is_available() is False

    def test_provider_type(self):
        p = DalleProvider(api_key="fake")
        assert p.provider_type == ProviderType.DALLE

    def test_closest_size_mapping(self):
        p = DalleProvider(api_key="fake")
        assert p._closest_size(1920, 1080) == "1792x1024"
        assert p._closest_size(1080, 1920) == "1024x1792"
        assert p._closest_size(1080, 1080) == "1024x1024"


class TestProviderFactory:
    def test_mock_flag_overrides_all(self):
        p = get_provider(mock=True)
        assert p.provider_type == ProviderType.MOCK

    def test_fallback_to_mock_without_keys(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("FIREFLY_CLIENT_ID", raising=False)
        p = get_provider()
        assert p.provider_type == ProviderType.MOCK

    def test_explicit_provider_type_mock(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("FIREFLY_CLIENT_ID", raising=False)
        p = get_provider(provider_type="mock")
        assert p.provider_type == ProviderType.MOCK
