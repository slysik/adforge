"""
Asset storage manager.

Handles:
  - Local file-based storage for input assets and generated outputs
  - Cache-aware: checks for existing generated assets to avoid re-generation
  - Organized output structure: output/<campaign>/<product>/<ratio>/
"""

from __future__ import annotations

import shutil
from pathlib import Path

from rich.console import Console

console = Console()


def slugify(text: str) -> str:
    """Convert text to filesystem-safe slug."""
    return (
        text.lower()
        .replace(" ", "_")
        .replace("&", "and")
        .replace("/", "-")
        .replace(":", "")
        .replace("'", "")
    )


class StorageManager:
    """Manages input/output asset storage on the local filesystem."""

    def __init__(
        self,
        input_dir: Path = Path("input_assets"),
        output_dir: Path = Path("output"),
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def get_campaign_dir(self, campaign_name: str) -> Path:
        d = self.output_dir / slugify(campaign_name)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_product_dir(self, campaign_name: str, product_id: str) -> Path:
        d = self.get_campaign_dir(campaign_name) / slugify(product_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def get_ratio_dir(self, campaign_name: str, product_id: str, ratio_name: str) -> Path:
        d = self.get_product_dir(campaign_name, product_id) / slugify(ratio_name)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def hero_output_path(
        self, campaign_name: str, product_id: str, ratio_name: str | None = None,
    ) -> Path:
        """Path for storing a generated hero image.

        If ratio_name is provided, stores a per-ratio hero. Otherwise stores
        a single base hero.
        """
        if ratio_name:
            d = self.get_ratio_dir(campaign_name, product_id, ratio_name)
            return d / "hero.png"
        d = self.get_product_dir(campaign_name, product_id)
        return d / "hero_base.png"

    def creative_output_path(
        self,
        campaign_name: str,
        product_id: str,
        ratio_name: str,
        language: str = "en",
    ) -> Path:
        """Path for the final composited creative."""
        d = self.get_ratio_dir(campaign_name, product_id, ratio_name)
        return d / f"creative_{language}.jpg"

    def find_existing_hero(self, product_id: str, hero_path: str | None) -> Path | None:
        """
        Look for an existing hero image:
          1. Explicit path from brief
          2. In input_assets/<product_id>.*
        """
        if hero_path:
            p = Path(hero_path)
            if p.exists():
                console.print(f"  [green]✓ Found existing hero: {p}[/green]")
                return p
            # Also check relative to input dir
            alt = self.input_dir / p.name
            if alt.exists():
                console.print(f"  [green]✓ Found existing hero: {alt}[/green]")
                return alt

        # Auto-discover in input_assets/
        for ext in ("*.png", "*.jpg", "*.jpeg", "*.webp"):
            matches = list(self.input_dir.glob(f"{slugify(product_id)}{ext.lstrip('*')}"))
            if matches:
                console.print(f"  [green]✓ Found existing hero: {matches[0]}[/green]")
                return matches[0]

        return None

    def copy_hero_to_output(self, src: Path, campaign_name: str, product_id: str) -> Path:
        """Copy an existing hero into the output tree."""
        dest = self.hero_output_path(campaign_name, product_id)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(src), str(dest))
        return dest
