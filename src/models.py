"""
Data models for the creative automation pipeline.
Uses Pydantic for validation and serialization.
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator, model_validator

# ---------------------------------------------------------------------------
# Supported ISO 639-1 language codes
# ---------------------------------------------------------------------------
SUPPORTED_LANGUAGES = {
    "en", "es", "fr", "de", "pt", "ja", "zh", "ko", "it", "nl",
    "ar", "hi", "ru", "sv", "da", "no", "fi", "pl", "tr", "th",
}

HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class AspectRatio(BaseModel):
    """Defines an output aspect ratio with pixel dimensions."""
    name: str = Field(..., min_length=1, description="Human-readable name, e.g. 'instagram_square'")
    ratio: str = Field(..., pattern=r"^\d+:\d+$", description="Ratio string, e.g. '1:1'")
    width: int = Field(..., gt=0, le=4096)
    height: int = Field(..., gt=0, le=4096)


class Product(BaseModel):
    """A product within the campaign."""
    id: str = Field(..., min_length=1, pattern=r"^[a-z0-9][a-z0-9\-]*$",
                    description="Unique slug (lowercase, hyphens allowed)")
    name: str = Field(..., min_length=1)
    description: str = Field(..., min_length=1)
    hero_image: Optional[str] = Field(
        None, description="Path to existing hero image, or null to generate"
    )
    keywords: list[str] = Field(default_factory=list)


class BrandGuidelines(BaseModel):
    """Brand-level constraints and assets."""
    primary_colors: list[str] = Field(
        default_factory=lambda: ["#000000", "#FFFFFF"],
        description="Hex color codes (#RRGGBB) for brand palette",
    )
    accent_color: Optional[str] = Field(
        None, description="Accent color used for secondary UI elements"
    )
    font_family: str = Field(
        "Arial", description="Preferred font family for text overlays"
    )
    logo_path: Optional[str] = None
    prohibited_words: list[str] = Field(default_factory=list)
    required_disclaimer: Optional[str] = Field(
        None, description="Legal disclaimer text rendered on every creative"
    )

    @field_validator("primary_colors", mode="after")
    @classmethod
    def validate_hex_colors(cls, v: list[str]) -> list[str]:
        for c in v:
            if not HEX_COLOR_RE.match(c):
                raise ValueError(f"Invalid hex color: '{c}'. Expected #RRGGBB format.")
        return v

    @field_validator("accent_color", mode="after")
    @classmethod
    def validate_accent_color(cls, v: str | None) -> str | None:
        if v is not None and not HEX_COLOR_RE.match(v):
            raise ValueError(f"Invalid accent hex color: '{v}'. Expected #RRGGBB format.")
        return v


class CampaignBrief(BaseModel):
    """Top-level campaign brief – the primary input to the pipeline."""
    name: str = Field(..., min_length=1)
    brand: str = Field(..., min_length=1)
    message: str = Field(..., min_length=1)
    tagline: Optional[str] = None
    target_region: str = Field(..., min_length=1)
    target_audience: str = Field(..., min_length=1)
    theme: Optional[str] = Field(default=None, description="Visual/local theme e.g. 'warm coastal'")
    languages: list[str] = Field(default_factory=lambda: ["en"])
    brand_guidelines: BrandGuidelines = Field(default_factory=BrandGuidelines)
    products: list[Product] = Field(..., min_length=2,
                                    description="At least two products required per campaign")
    aspect_ratios: list[AspectRatio] = Field(
        default_factory=lambda: [
            AspectRatio(name="instagram_square", ratio="1:1", width=1080, height=1080),
            AspectRatio(name="stories", ratio="9:16", width=1080, height=1920),
            AspectRatio(name="facebook_landscape", ratio="16:9", width=1920, height=1080),
        ],
        min_length=3,
        description="At least three aspect ratios required",
    )

    @field_validator("languages", mode="after")
    @classmethod
    def validate_languages(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("At least one language is required.")
        unknown = [lang for lang in v if lang not in SUPPORTED_LANGUAGES]
        if unknown:
            raise ValueError(
                f"Unsupported language codes: {unknown}. "
                f"Supported: {sorted(SUPPORTED_LANGUAGES)}"
            )
        if len(v) != len(set(v)):
            raise ValueError(f"Duplicate language codes: {v}")
        return v

    @model_validator(mode="after")
    def validate_unique_product_ids(self) -> CampaignBrief:
        ids = [p.id for p in self.products]
        if len(ids) != len(set(ids)):
            dupes = [pid for pid in ids if ids.count(pid) > 1]
            raise ValueError(f"Duplicate product IDs: {set(dupes)}")
        return self


# ---------------------------------------------------------------------------
# Pipeline result models
# ---------------------------------------------------------------------------

class ComplianceStatus(str, Enum):
    """Three-valued compliance result with explicit semantics."""
    PASSED = "passed"
    WARNING = "warning"
    NOT_CHECKED = "not_checked"
    FAILED = "failed"


class AssetStatus(str, Enum):
    REUSED = "reused"
    GENERATED = "generated"
    FAILED = "failed"


class ComplianceResult(BaseModel):
    """Evidence-backed compliance check result."""
    status: ComplianceStatus
    notes: list[str] = Field(default_factory=list)


class GeneratedAsset(BaseModel):
    """Metadata for a single generated creative asset."""
    product_id: str
    aspect_ratio: str
    language: str
    file_path: str
    status: AssetStatus
    hero_status: AssetStatus
    prompt_used: Optional[str] = None
    brand_compliance: ComplianceResult = Field(
        default_factory=lambda: ComplianceResult(status=ComplianceStatus.NOT_CHECKED)
    )
    legal_compliance: ComplianceResult = Field(
        default_factory=lambda: ComplianceResult(status=ComplianceStatus.NOT_CHECKED)
    )
    rendered_texts: list[str] = Field(
        default_factory=list,
        description="All text strings actually rendered on this creative",
    )


class PipelineResult(BaseModel):
    """Aggregate result from running the full pipeline."""
    campaign_name: str
    total_assets: int = 0
    created_count: int = 0
    hero_reused_count: int = 0
    failed_count: int = 0
    assets: list[GeneratedAsset] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    elapsed_seconds: float = 0.0
