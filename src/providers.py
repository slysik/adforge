"""
Image generation provider abstraction.

Business Value:
  Eliminates vendor lock-in and reduces per-asset generation costs by enabling
  instant provider switching without code changes. The pipeline always runs —
  even without API keys — so demos, tests, and CI never block on credentials.

Purpose:
  Provide a unified ImageProvider interface that decouples the pipeline from
  any single GenAI vendor. The factory auto-resolves the best available provider
  at runtime via a preference chain: Firefly → Gemini → Mock.

Description:
  Four concrete providers implement the same generate() contract:

  1. Adobe Firefly Services (production) — Text-to-Image, Generative Expand
     for aspect-ratio adaptation, and Style Reference for brand consistency.
     Requires FIREFLY_CLIENT_ID / FIREFLY_CLIENT_SECRET.
  2. Google Imagen 4.0 (primary fallback) — native aspect-ratio support via
     the google-genai SDK. Requires GEMINI_API_KEY.
  3. OpenAI DALL-E 3 (explicit selection only) — three fixed sizes, resized
     to target dimensions after generation. Requires OPENAI_API_KEY.
  4. Mock provider (testing) — deterministic procedural images using brand
     colors from the prompt. Zero cost, fully repeatable.

  All providers return (PIL.Image, GenerationMetadata) so downstream modules
  (compositor, validator) are completely provider-agnostic. Transient API
  failures are handled via exponential backoff with jitter.
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
#
# Business Value:  Prevents pipeline failures from costing time and money when
#                  a single transient API hiccup would otherwise abort an
#                  entire 18-asset generation run.
# Purpose:         Wrap any callable with automatic retry, distinguishing
#                  transient errors (rate limits, server errors, network)
#                  from permanent ones (bad input, auth failures).
# Description:     Exponential backoff with jitter:
#                    delay = min(base * 2^attempt + random(0, base * 2^attempt), max)
#                  Retries ConnectionError, TimeoutError, HTTP 429/5xx.
#                  Does NOT retry ValueError, HTTP 4xx (except 429).
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
    exp_delay = base_delay * (2**attempt)
    jitter = random.uniform(0, exp_delay)
    delay = min(exp_delay + jitter, max_delay)
    console.print(f"  [dim]Retrying in {delay:.1f}s…[/dim]")
    time.sleep(delay)


# ---------------------------------------------------------------------------
# Provider metadata
#
# Business Value:  Enables per-asset cost tracking and performance dashboards
#                  so campaign managers can optimize spend across providers.
# Purpose:         Carry provider, model, timing, and cost data alongside
#                  every generated image through the pipeline.
# Description:     Immutable dataclass returned by every provider's generate()
#                  method. Downstream modules (tracker, report) consume this
#                  without needing to know which provider created the asset.
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
#
# Business Value:  Makes the pipeline vendor-agnostic — new providers can be
#                  added without touching orchestration or composition code.
# Purpose:         Define the contract every image provider must fulfill:
#                  generate() → (PIL.Image, GenerationMetadata).
# Description:     ABC with three abstract members (provider_type, model_name,
#                  generate) and an optional is_available() check. The factory
#                  function get_provider() uses is_available() to auto-resolve
#                  the best provider at runtime.
# ---------------------------------------------------------------------------


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
#
# Business Value:  Targets the production-grade GenAI platform used by creative
#                  teams at scale. Firefly's Generative Expand eliminates
#                  cropping artifacts when adapting assets across aspect ratios,
#                  saving manual design rework.
# Purpose:         Primary provider — implements Text-to-Image and Generative
#                  Expand via the Firefly Services REST API, plus Style
#                  Reference for brand-consistent generation.
# Description:     Authenticates via Adobe IMS client_credentials grant.
#                  Maps requested dimensions to the nearest Firefly-supported
#                  size, generates the image, then resizes to exact target.
#                  The expand() method adapts existing assets to new aspect
#                  ratios by generating contextually consistent edge content.
#                  Falls back gracefully when credentials are absent.
#
#                  Env vars: FIREFLY_CLIENT_ID, FIREFLY_CLIENT_SECRET,
#                            FIREFLY_IMS_ORG_ID (optional, enterprise).
#                  Pricing: ~$0.04/standard, ~$0.08/premium generation.
# ---------------------------------------------------------------------------


class FireflyProvider(ImageProvider):
    """Adobe Firefly Services provider — production-grade image generation."""

    GENERATE_ENDPOINT = "https://firefly-api.adobe.io/v3/images/generate"
    EXPAND_ENDPOINT = "https://firefly-api.adobe.io/v3/images/expand"
    TOKEN_ENDPOINT = "https://ims-na1.adobelogin.com/ims/token/v3"

    # Firefly supports these sizes natively
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

        console.print(
            f"  [magenta]Calling Firefly Services ({gen_w}×{gen_h})…[/magenta]"
        )

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

        def _expand_request():
            resp = requests.post(
                self.EXPAND_ENDPOINT,
                headers=headers,
                json=body,
                timeout=120,
            )
            resp.raise_for_status()
            return resp.json()

        data = _retry_api_call(_expand_request)

        image_url = data["outputs"][0]["image"]["url"]

        def _download_expanded():
            return requests.get(image_url, timeout=120).content

        img_bytes = _retry_api_call(_download_expanded)
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
#
# Business Value:  Provides access to OpenAI's image generation when Firefly
#                  or Gemini are not available or when creative teams want to
#                  compare outputs across providers.
# Purpose:         Explicit-selection provider — used only when the caller
#                  specifies provider_type="dalle". Not part of the auto-detect
#                  fallback chain.
# Description:     DALL-E 3 supports only three fixed sizes (1024x1024,
#                  1024x1792, 1792x1024). The provider picks the closest match
#                  by aspect ratio, generates the image, then resizes to exact
#                  target dimensions via Lanczos resampling.
#
#                  Env vars: OPENAI_API_KEY
#                  Pricing: ~$0.04/standard, ~$0.08/HD generation.
# ---------------------------------------------------------------------------

DALLE3_SIZES = {
    "1:1": "1024x1024",
    "9:16": "1024x1792",
    "16:9": "1792x1024",
}


class DalleProvider(ImageProvider):
    """OpenAI DALL-E 3 provider — explicit selection only, not auto-detected."""

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
#
# Business Value:  Offers a free-tier entry point for development and the
#                  widest native aspect-ratio support (5 ratios), reducing
#                  post-generation resize distortion compared to DALL-E.
# Purpose:         Primary fallback when Firefly credentials are absent.
#                  Second in the auto-detect chain: Firefly → Gemini → Mock.
# Description:     Uses the google-genai SDK to call Imagen 4.0. Picks the
#                  closest native aspect ratio (1:1, 9:16, 16:9, 3:4, 4:3)
#                  then resizes to exact target dimensions if needed.
#
#                  Env vars: GEMINI_API_KEY or NANO_BANANA_API_KEY
#                  Pricing: free tier available, then per-image.
# ---------------------------------------------------------------------------

IMAGEN_RATIOS = {"1:1", "9:16", "16:9", "3:4", "4:3"}


class GeminiProvider(ImageProvider):
    """Google Imagen 4.0 provider — primary fallback in the auto-detect chain."""

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
#
# Business Value:  Enables the full pipeline demo, CI/CD, and test suite to
#                  run without any API keys or network access — zero cost,
#                  instant feedback, no rate-limit risk.
# Purpose:         Last resort in the auto-detect chain and the default for
#                  testing. Produces deterministic images so test assertions
#                  are stable across runs.
# Description:     Generates procedural product-style images using brand
#                  colors extracted from the prompt (or a hash-derived
#                  palette as fallback). Output is label-free and watermark-
#                  free. Same (PIL.Image, GenerationMetadata) contract as
#                  real providers — downstream modules are unaware they are
#                  consuming mock output.
# ---------------------------------------------------------------------------

# Canonical dimensions for mock mode per aspect ratio
MOCK_DIMS = {
    "1:1": (1080, 1080),
    "9:16": (1080, 1920),
    "16:9": (1920, 1080),
}


class MockProvider(ImageProvider):
    """Deterministic mock provider — zero cost, fully repeatable output."""

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
        product_name = (
            prompt.split("Product: ")[-1].split(" – ")[0]
            if "Product:" in prompt
            else prompt[:30]
        )
        img = self._procedural_image(product_name, width, height, prompt)

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
    def _parse_brand_colors(prompt: str) -> list[tuple[int, int, int]]:
        """Extract hex colors from the 'Brand color palette:' clause in the prompt."""
        import re

        match = re.search(r"Brand color palette:\s*([^.]+)\.", prompt)
        if not match:
            return []
        hex_codes = re.findall(r"#([0-9A-Fa-f]{6})", match.group(1))
        return [(int(h[:2], 16), int(h[2:4], 16), int(h[4:6], 16)) for h in hex_codes]

    @staticmethod
    def _procedural_image(
        product_name: str, w: int, h: int, prompt: str = ""
    ) -> Image.Image:
        """Generate a clean procedural product image using brand colors when available."""
        from colorsys import hsv_to_rgb, rgb_to_hsv

        # Try to use brand colors from the prompt
        brand_rgbs = MockProvider._parse_brand_colors(prompt)

        digest = hashlib.md5(product_name.encode()).hexdigest()
        shape_variant = int(digest[4:6], 16)

        if len(brand_rgbs) >= 2:
            # Use actual brand colors: first for background (lightened), second for product, last for accent
            def lighten(rgb, factor=0.85):
                return tuple(int(c + (255 - c) * factor) for c in rgb)

            bg = lighten(brand_rgbs[0], 0.75)
            prod_color = brand_rgbs[1] if len(brand_rgbs) > 1 else brand_rgbs[0]
            accent = brand_rgbs[-1] if len(brand_rgbs) > 2 else brand_rgbs[0]
        else:
            # Fallback: deterministic from product name
            hue = int(digest[:2], 16) / 255.0
            sat_seed = int(digest[2:4], 16) / 255.0
            r, g, b = hsv_to_rgb(hue, 0.15 + sat_seed * 0.15, 0.95)
            bg = (int(r * 255), int(g * 255), int(b * 255))
            r2, g2, b2 = hsv_to_rgb(hue, 0.4 + sat_seed * 0.3, 0.85)
            prod_color = (int(r2 * 255), int(g2 * 255), int(b2 * 255))
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
                fill=None,
                outline=(255, 255, 255, alpha),
                width=4,
            )

        # Central product shape
        shape_seed = shape_variant % 3
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
                radius=int(w * 0.04),
                fill=prod_color + (230,),
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
                [
                    cx - int(jar_r * 0.7),
                    cy - jar_r - int(h * 0.04),
                    cx + int(jar_r * 0.7),
                    cy - jar_r + int(h * 0.02),
                ],
                fill=accent + (180,),
            )
            draw.ellipse(
                [
                    cx - int(jar_r * 0.5),
                    cy - int(jar_r * 0.5),
                    cx + int(jar_r * 0.2),
                    cy + int(jar_r * 0.2),
                ],
                fill=(255, 255, 255, 40),
            )
        else:
            draw.rounded_rectangle(
                [margin_x, margin_top, w - margin_x, h - margin_bot],
                radius=int(w * 0.02),
                fill=prod_color + (230,),
            )
            panel_x = cx - int(w * 0.05)
            draw.line(
                [(panel_x, margin_top + 10), (panel_x, h - margin_bot - 10)],
                fill=accent + (100,),
                width=3,
            )
            draw.polygon(
                [
                    (margin_x, margin_top),
                    (cx, margin_top - int(h * 0.05)),
                    (w - margin_x, margin_top),
                ],
                fill=prod_color + (200,),
            )

        # Accent circles
        for i in range(5):
            seed_val = int(digest[6 + i * 2 : 8 + i * 2], 16)
            ax = int((seed_val / 255) * w)
            ay = int((int(digest[8 + i * 2 : 10 + i * 2], 16) / 255) * h)
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
#
# Business Value:  Guarantees the pipeline always runs regardless of which
#                  API keys are available — demos never fail, production
#                  uses the best provider, and tests use mock automatically.
# Purpose:         Single entry point for provider resolution. Handles both
#                  explicit selection (fail loudly) and auto-detection
#                  (degrade gracefully).
# Description:     Resolution order:
#                    1. mock=True or provider_type="mock" → MockProvider
#                    2. Explicit provider_type → that provider (raises if
#                       credentials are missing)
#                    3. Auto-detect: Firefly → Gemini → Mock (with warning)
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
