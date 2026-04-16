"""
Image generation provider abstraction.

Unified ImageProvider interface that decouples the pipeline from any single
GenAI vendor. The factory auto-resolves the best available provider at
runtime via a preference chain: Firefly → Gemini → Mock.

All providers return (PIL.Image, GenerationMetadata) so downstream modules
(compositor, validator) are completely provider-agnostic. Transient API
failures are handled via exponential backoff with jitter (see retry.py).
"""

from __future__ import annotations

import io
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

from PIL import Image
from rich.console import Console

from .mock_drawing import procedural_image
from .retry import retry_api_call

console = Console()


@dataclass
class GenerationMetadata:
    """Metadata returned by every provider alongside the generated image."""

    provider: str
    model: str
    prompt_used: str
    generation_time_ms: int = 0
    estimated_cost_usd: float = 0.0
    aspect_ratio: str = ""
    raw_response: dict = field(default_factory=dict)


class ProviderType(str, Enum):
    """Available image generation providers."""

    FIREFLY = "firefly"
    DALLE = "dalle"
    GEMINI = "gemini"
    MOCK = "mock"


class ImageProvider(ABC):
    """Abstract image generation provider.

    All providers implement the same interface so the pipeline is
    provider-agnostic. Swap providers via configuration, not code changes.
    """

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType: ...

    @property
    @abstractmethod
    def model_name(self) -> str: ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        width: int,
        height: int,
        output_path: Path,
        style_reference: Optional[Path] = None,
    ) -> tuple[Image.Image, GenerationMetadata]:
        """Generate an image from a text prompt.

        Returns (PIL Image, GenerationMetadata).
        """
        ...

    def is_available(self) -> bool:
        """Check if this provider can be used (credentials present, etc.)."""
        return True


class FireflyProvider(ImageProvider):
    """Adobe Firefly Services — production-grade image generation.

    Authenticates via Adobe IMS client_credentials grant. Maps requested
    dimensions to the nearest Firefly-supported size, generates the image,
    then resizes to exact target. Also supports Style Reference for brand
    consistency and Generative Expand for aspect-ratio adaptation.
    """

    GENERATE_ENDPOINT = "https://firefly-api.adobe.io/v3/images/generate"
    TOKEN_ENDPOINT = "https://ims-na1.adobelogin.com/ims/token/v3"

    SUPPORTED_SIZES = {
        (1024, 1024),
        (1152, 896),
        (896, 1152),
        (1024, 1408),
        (1408, 1024),
        (1024, 1792),
        (1792, 1024),
    }

    def __init__(self):
        self.client_id = os.getenv("FIREFLY_CLIENT_ID")
        self.client_secret = os.getenv("FIREFLY_CLIENT_SECRET")
        self.ims_org = os.getenv("FIREFLY_IMS_ORG_ID")
        self._access_token: Optional[str] = None
        self._token_expires: float = 0

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.FIREFLY

    @property
    def model_name(self) -> str:
        return "firefly-v3"

    def is_available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_access_token(self) -> str:
        """Obtain or refresh an IMS access token via client_credentials grant."""
        if self._access_token and time.time() < self._token_expires:
            return self._access_token

        import requests

        response = requests.post(
            self.TOKEN_ENDPOINT,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "openid,AdobeID,firefly_api",
            },
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        self._access_token = data["access_token"]
        self._token_expires = time.time() + data.get("expires_in", 3600) - 60
        return self._access_token

    def _find_nearest_size(self, width: int, height: int) -> tuple[int, int]:
        """Find the nearest Firefly-supported size by aspect ratio."""
        return min(
            self.SUPPORTED_SIZES,
            key=lambda s: abs(s[0] / s[1] - width / height),
        )

    def generate(
        self,
        prompt: str,
        width: int,
        height: int,
        output_path: Path,
        style_reference: Optional[Path] = None,
    ) -> tuple[Image.Image, GenerationMetadata]:
        """Generate via Adobe Firefly Services API."""
        import requests

        start = time.time()
        token = self._get_access_token()
        gen_w, gen_h = self._find_nearest_size(width, height)

        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.client_id,
            "Content-Type": "application/json",
        }

        body = {
            "prompt": prompt,
            "n": 1,
            "size": {"width": gen_w, "height": gen_h},
            "contentClass": "photo",
            "styles": {"presets": ["photo_real"]},
        }

        # Style reference for brand consistency
        if style_reference and style_reference.exists():
            import base64

            ref_bytes = style_reference.read_bytes()
            body["style"] = {
                "imageReference": {
                    "source": {
                        "type": "base64",
                        "data": base64.b64encode(ref_bytes).decode(),
                    }
                },
                "strength": 60,
            }

        console.print(
            f"  [magenta]Calling Firefly Services ({gen_w}×{gen_h})…[/magenta]"
        )

        def make_request():
            response = requests.post(
                self.GENERATE_ENDPOINT,
                headers=headers,
                json=body,
                timeout=120,
            )
            response.raise_for_status()
            return response.json()

        data = retry_api_call(make_request)

        image_url = data["outputs"][0]["image"]["url"]

        def download_image():
            return requests.get(image_url, timeout=120).content

        img_bytes = retry_api_call(download_image)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        if img.size != (width, height):
            img = img.resize((width, height), Image.LANCZOS)

        elapsed_ms = int((time.time() - start) * 1000)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "PNG")

        meta = GenerationMetadata(
            provider="firefly",
            model="firefly-v3",
            prompt_used=prompt,
            generation_time_ms=elapsed_ms,
            estimated_cost_usd=0.04,
            aspect_ratio=f"{width}:{height}",
            raw_response={"seed": data["outputs"][0].get("seed")},
        )

        return img, meta


class DalleProvider(ImageProvider):
    """OpenAI DALL-E 3 — explicit selection only, not in the auto-detect chain.

    DALL-E 3 supports three fixed sizes (1024x1024, 1024x1792, 1792x1024).
    Picks the closest match by aspect ratio, then resizes to exact target.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI

                self._client = OpenAI(api_key=self.api_key)
            except ImportError:
                console.print(
                    "[yellow]⚠ openai package not installed — DALL-E unavailable.[/yellow]"
                )
            except Exception as exc:
                console.print(
                    f"[yellow]⚠ OpenAI init failed ({exc}) — DALL-E unavailable.[/yellow]"
                )

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.DALLE

    @property
    def model_name(self) -> str:
        return "dall-e-3"

    def is_available(self) -> bool:
        return self._client is not None

    def _closest_size(self, width: int, height: int) -> str:
        ratio = width / height
        if ratio > 1.3:
            return "1792x1024"
        elif ratio < 0.7:
            return "1024x1792"
        return "1024x1024"

    def generate(
        self,
        prompt: str,
        width: int,
        height: int,
        output_path: Path,
        style_reference: Optional[Path] = None,
    ) -> tuple[Image.Image, GenerationMetadata]:
        """Generate via OpenAI DALL-E 3 API."""
        import requests as req

        start = time.time()
        size = self._closest_size(width, height)
        console.print(f"  [cyan]Calling DALL-E 3 ({size})…[/cyan]")

        def generate_image():
            return self._client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size=size,
                quality="standard",
            )

        response = retry_api_call(generate_image)

        image_url = response.data[0].url

        def download_image():
            return req.get(image_url, timeout=120).content

        img_bytes = retry_api_call(download_image)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        if img.size != (width, height):
            img = img.resize((width, height), Image.LANCZOS)

        elapsed_ms = int((time.time() - start) * 1000)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "PNG")

        meta = GenerationMetadata(
            provider="dalle",
            model="dall-e-3",
            prompt_used=prompt,
            generation_time_ms=elapsed_ms,
            estimated_cost_usd=0.04,
            aspect_ratio=f"{width}:{height}",
        )

        return img, meta


class GeminiProvider(ImageProvider):
    """Google Imagen 4.0 — primary fallback when Firefly is unavailable.

    Supports 5 native aspect ratios (1:1, 9:16, 16:9, 3:4, 4:3), reducing
    post-generation resize distortion compared to DALL-E.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = (
            api_key or os.getenv("GEMINI_API_KEY") or os.getenv("NANO_BANANA_API_KEY")
        )
        self._client = None
        if self.api_key:
            try:
                from google import genai

                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                console.print(
                    "[yellow]⚠ google-genai package not installed — Gemini unavailable.[/yellow]"
                )
            except Exception as exc:
                console.print(
                    f"[yellow]⚠ Gemini init failed ({exc}) — Gemini unavailable.[/yellow]"
                )

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.GEMINI

    @property
    def model_name(self) -> str:
        return "imagen-4.0"

    def is_available(self) -> bool:
        return self._client is not None

    def _closest_ratio(self, width: int, height: int) -> str:
        """Find the closest Imagen-supported aspect ratio."""
        ratio = width / height
        candidates = {
            "1:1": 1.0,
            "16:9": 16 / 9,
            "9:16": 9 / 16,
            "4:3": 4 / 3,
            "3:4": 3 / 4,
        }
        return min(candidates, key=lambda k: abs(candidates[k] - ratio))

    def generate(
        self,
        prompt: str,
        width: int,
        height: int,
        output_path: Path,
        style_reference: Optional[Path] = None,
    ) -> tuple[Image.Image, GenerationMetadata]:
        """Generate via Google Imagen 4.0 API."""
        from google.genai import types

        start = time.time()
        aspect_ratio = self._closest_ratio(width, height)
        console.print(f"  [blue]Calling Imagen 4.0 ({aspect_ratio})…[/blue]")

        def generate_image():
            return self._client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                ),
            )

        response = retry_api_call(generate_image)

        if not response.generated_images:
            raise RuntimeError("Imagen returned no images")

        img_bytes = response.generated_images[0].image.image_bytes
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        if img.size != (width, height):
            img = img.resize((width, height), Image.LANCZOS)

        elapsed_ms = int((time.time() - start) * 1000)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "PNG")

        meta = GenerationMetadata(
            provider="gemini",
            model="imagen-4.0",
            prompt_used=prompt,
            generation_time_ms=elapsed_ms,
            estimated_cost_usd=0.04,
            aspect_ratio=f"{width}:{height}",
        )

        return img, meta


class MockProvider(ImageProvider):
    """Deterministic mock provider — zero cost, fully repeatable output.

    Generates procedural product-style images using brand colors from the
    prompt (or a hash-derived palette). Enables demos, CI/CD, and tests
    to run without API keys or network access.
    """

    @property
    def provider_type(self) -> ProviderType:
        return ProviderType.MOCK

    @property
    def model_name(self) -> str:
        return "mock-v1"

    def generate(
        self,
        prompt: str,
        width: int,
        height: int,
        output_path: Path,
        style_reference: Optional[Path] = None,
    ) -> tuple[Image.Image, GenerationMetadata]:
        """Generate a deterministic procedural image."""
        start = time.time()

        product_name = (
            prompt.split("Product: ")[-1].split(" – ")[0]
            if "Product:" in prompt
            else prompt[:30]
        )
        img = procedural_image(product_name, width, height, prompt)

        elapsed_ms = int((time.time() - start) * 1000)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "PNG")

        meta = GenerationMetadata(
            provider="mock",
            model="mock-v1",
            prompt_used=prompt,
            generation_time_ms=elapsed_ms,
            estimated_cost_usd=0.0,
            aspect_ratio=f"{width}:{height}",
        )

        return img, meta


def get_provider(
    provider_type: Optional[str] = None,
    api_key: Optional[str] = None,
    mock: bool = False,
) -> ImageProvider:
    """Resolve the best available image generation provider.

    Resolution: Firefly → Gemini → Mock (auto-detect), or fail loudly
    when a specific provider is requested but unavailable.
    """
    if mock or provider_type == ProviderType.MOCK.value:
        return MockProvider()

    # Explicit provider selection — fail loudly if unavailable
    if provider_type == ProviderType.FIREFLY.value:
        provider = FireflyProvider()
        if provider.is_available():
            return provider
        raise RuntimeError(
            "Firefly provider selected but FIREFLY_CLIENT_ID / FIREFLY_CLIENT_SECRET not set."
        )

    if provider_type == ProviderType.DALLE.value:
        provider = DalleProvider(api_key=api_key)
        if provider.is_available():
            return provider
        raise RuntimeError("DALL-E provider selected but OPENAI_API_KEY not set.")

    if provider_type == ProviderType.GEMINI.value:
        provider = GeminiProvider(api_key=api_key)
        if provider.is_available():
            return provider
        raise RuntimeError(
            "Gemini provider selected but GEMINI_API_KEY / NANO_BANANA_API_KEY not set."
        )

    # Auto-detect: try each provider in preference order
    firefly = FireflyProvider()
    if firefly.is_available():
        console.print("[magenta]Using Adobe Firefly Services[/magenta]")
        return firefly

    gemini = GeminiProvider(api_key=api_key)
    if gemini.is_available():
        console.print("[blue]Using Google Imagen 4.0[/blue]")
        return gemini

    console.print("[yellow]⚠ No API keys found – using mock mode.[/yellow]")
    return MockProvider()
