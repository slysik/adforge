"""
Reusable UI components, constants, and shared helpers for the AdForge Streamlit app.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from src.templates import LayoutTemplate, TEMPLATE_RENDERERS, auto_select_template

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SAMPLE_BRIEFS = {
    "Coastal Collection 2025 (Blue Beach House Designs)": "sample_briefs/beach_house_campaign.yaml",
    "Holiday Glow 2025 (LuxeBeauty)": "sample_briefs/holiday_campaign.yaml",
}

DEFAULT_BUILDER_PRODUCTS = [
    {
        "id": "resort-shell-handbag",
        "name": "Resort Shell Handbag",
        "description": (
            "Handcrafted rattan handbag adorned with natural seashells and floral accents, "
            "featuring a lined interior, drawstring closure, and room for all your essentials"
        ),
        "keywords": "shell handbag, rattan bag, coastal fashion, beach accessory, resort wear, handcrafted, seashell",
    },
    {
        "id": "cowrie-shell-box",
        "name": "Bespoke Rattan Cowrie Shell Box",
        "description": (
            "Hand-woven rattan keepsake box embellished with cowrie shells and turquoise accents, "
            "perfect for jewelry storage or coastal home decor"
        ),
        "keywords": "cowrie shell, rattan box, keepsake box, coastal decor, jewelry box, handwoven",
    },
    {
        "id": "painted-shell-art",
        "name": "Painted Shell Art",
        "description": (
            "Vibrant hand-painted seashell collection displayed in a gilded bamboo frame, "
            "featuring pastel rainbow scallops, starfish, and sand dollars"
        ),
        "keywords": "shell art, wall art, coastal wall decor, painted shells, framed art, pastel decor",
    },
]

COMPLIANCE_EMOJI = {
    "passed": "✅",
    "warning": "⚠️",
    "failed": "❌",
    "not_checked": "—",
}

TEMPLATE_INFO = {
    LayoutTemplate.PRODUCT_HERO: {
        "label": "Product Hero",
        "desc": "Full-bleed hero image with gradient overlay and text at bottom. Universally safe.",
        "icon": "🖼️",
    },
    LayoutTemplate.EDITORIAL: {
        "label": "Editorial",
        "desc": "60/40 hero–panel split with magazine-style text block. Best for longer messages.",
        "icon": "📰",
    },
    LayoutTemplate.SPLIT_PANEL: {
        "label": "Split Panel",
        "desc": "50/50 image and branded text panel. Auto-adapts orientation to format.",
        "icon": "📐",
    },
    LayoutTemplate.MINIMAL: {
        "label": "Minimal",
        "desc": "Centered hero at 60% scale with generous whitespace. Premium feel.",
        "icon": "✨",
    },
    LayoutTemplate.BOLD_TYPE: {
        "label": "Bold Type",
        "desc": "Oversized typography over tinted hero background. Punchy and direct.",
        "icon": "🔤",
    },
}

PIPELINE_STAGES = [
    ("1", "Brief\nIngestion"),
    ("2", "Analysis"),
    ("3", "Asset\nResolution"),
    ("4", "Hero\nGeneration"),
    ("5", "Layout\nRendering"),
    ("6", "Policy\nChecks"),
    ("7", "Reporting"),
]


def log_run(
    campaign: str,
    provider: str,
    total: int,
    created: int,
    failed: int,
    elapsed: float,
    time_saved_hrs: float,
):
    from datetime import datetime

    st.session_state.run_log.insert(
        0,
        {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "campaign": campaign,
            "provider": provider,
            "total": total,
            "created": created,
            "failed": failed,
            "elapsed": f"{elapsed:.1f}s",
            "time_saved": f"{time_saved_hrs:.1f}h",
        },
    )


# ---------------------------------------------------------------------------
# Reusable UI widgets
# ---------------------------------------------------------------------------


def render_hero_header(
    title: str,
    subtitle: str,
    compact: bool = False,
):
    """Render the main page header in expanded or compact mode."""
    if compact:
        st.markdown(
            f'<div class="af-hero" style="padding:.5rem 1.2rem;margin-bottom:.3rem">'
            f'<h1 style="font-size:1.1rem !important">🎨 {title}</h1>'
            f"</div>",
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="af-hero">
              <h1>🎨 {title}</h1>
              <p>{subtitle}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_pipeline_stepper(
    active_stage: int = 0,
    done_stages: int = 0,
    target=None,
):
    """Render a horizontal 7-step pipeline progress indicator."""
    steps_html = ""
    for idx, (num, label) in enumerate(PIPELINE_STAGES):
        stage_num = idx + 1
        if stage_num < active_stage or stage_num <= done_stages:
            cls = "done"
            circle = "✓"
        elif stage_num == active_stage:
            cls = "active"
            circle = num
        else:
            cls = ""
            circle = num
        label_safe = label.replace("\n", "<br>")
        steps_html += (
            f'<div class="af-step {cls}">'
            f'<div class="af-step-circle">{circle}</div>'
            f'<div class="af-step-label">{label_safe}</div>'
            f"</div>"
        )
    render_target = target or st
    render_target.markdown(
        f'<div class="af-stepper">{steps_html}</div>',
        unsafe_allow_html=True,
    )


def render_metric_cards(metrics: list[dict]):
    """Render branded metric cards.
    Each dict: {label, value, sub, icon, bar_pct (0-100, optional)}
    """
    cards_html = '<div class="af-metric-grid">'
    for m in metrics:
        bar_html = ""
        pct = m.get("bar_pct")
        if pct is not None:
            bar_html = (
                f'<div class="af-metric-bar">'
                f'<div class="af-metric-bar-fill" style="width:{min(pct, 100):.0f}%"></div>'
                f"</div>"
            )
        cards_html += (
            f'<div class="af-metric-card">'
            f'<div class="af-metric-card-icon">{m.get("icon", "")}</div>'
            f'<div class="af-metric-label">{m["label"]}</div>'
            f'<div class="af-metric-value">{m["value"]}</div>'
            f'<div class="af-metric-sub">{m.get("sub", "")}</div>'
            f"{bar_html}"
            f"</div>"
        )
    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)


def render_section_title(text: str):
    st.markdown(f'<div class="af-section-title">{text}</div>', unsafe_allow_html=True)


def place_logo_on_canvas(canvas, logo_path: str | None):
    """Place logo in top-right corner for preview mode."""
    from PIL import Image as PILImage

    if not logo_path or not Path(logo_path).exists():
        return canvas
    logo = PILImage.open(logo_path).convert("RGBA")
    w, h = canvas.size
    logo_max = int(min(w, h) * 0.12)
    logo.thumbnail((logo_max, logo_max), PILImage.LANCZOS)
    padding = int(w * 0.04)
    canvas.paste(logo, (w - logo.width - padding, padding), logo)
    return canvas


def render_ab_comparison(brief, sample_hero_path: Path | None = None):
    from PIL import Image as PILImage

    if sample_hero_path is None or not sample_hero_path.exists():
        st.info(
            "No hero image available for A/B preview. Run the pipeline first or provide a hero asset."
        )
        return

    hero = PILImage.open(str(sample_hero_path)).convert("RGBA")
    bg = brief.brand_guidelines
    logo_path = getattr(bg, "logo_path", None)

    ratio = brief.aspect_ratios[0]
    st.caption(f"Preview at **{ratio.ratio}** ({ratio.width}×{ratio.height})")

    cols = st.columns(len(TEMPLATE_RENDERERS))
    for col, (template, renderer) in zip(cols, TEMPLATE_RENDERERS.items()):
        info = TEMPLATE_INFO.get(template, {"label": template.value, "icon": "📄"})
        with col:
            try:
                canvas, _ = renderer(
                    hero=hero.copy(),
                    width=ratio.width,
                    height=ratio.height,
                    message=brief.message,
                    tagline=brief.tagline,
                    brand_name=brief.brand,
                    font_family=bg.font_family,
                    brand_colors=bg.primary_colors,
                    accent_color=bg.accent_color,
                )
                canvas = place_logo_on_canvas(canvas, logo_path)
                st.image(
                    canvas.convert("RGB"),
                    caption=f"{info['icon']} {info['label']}",
                    use_container_width=True,
                )
            except Exception as e:
                st.error(f"{info['label']}: {e}")

        auto = auto_select_template(
            ratio.ratio, brief.products[0].keywords, brief.message
        )
        if template == auto:
            with col:
                st.success("Auto-selected")


# ---------------------------------------------------------------------------
# Shared utilities
# ---------------------------------------------------------------------------


def load_sample_report(campaign_dir: Path) -> dict | None:
    report_path = campaign_dir / "report.json"
    if report_path.exists():
        return json.loads(report_path.read_text())
    return None


def find_sample_campaigns(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted(
        [d for d in base.iterdir() if d.is_dir() and (d / "report.json").exists()]
    )


def score_asset(asset: dict) -> float:
    """Score a creative for AI-pick ranking. Higher = better."""
    score = 50.0
    brand = asset.get("brand_compliance", {}).get("status", "not_checked")
    legal = asset.get("legal_compliance", {}).get("status", "not_checked")
    hero = asset.get("hero_status", "generated")
    ratio = asset.get("aspect_ratio", "")

    if brand == "passed":
        score += 20
    elif brand == "warning":
        score += 5
    elif brand == "failed":
        score -= 15
    if legal == "passed":
        score += 20
    elif legal == "warning":
        score += 5
    elif legal == "failed":
        score -= 15

    if hero == "generated":
        score += 10
    if "1:1" in ratio:
        score += 5
    elif "9:16" in ratio:
        score += 3

    fp = asset.get("file_path", "")
    if fp and Path(fp).exists():
        size_kb = Path(fp).stat().st_size / 1024
        score += min(10, size_kb / 50)

    return score


def analysis_to_payload(analysis) -> dict:
    """Normalize analyzer output for the shared UI components."""
    return {
        "score": {
            "overall": analysis.score.overall,
            "completeness": analysis.score.completeness,
            "clarity": analysis.score.clarity,
            "brand_strength": analysis.score.brand_strength,
            "targeting": analysis.score.targeting,
        },
        "strengths": analysis.strengths,
        "weaknesses": analysis.weaknesses,
    }


def estimate_time_saved_hours(created_count: int, elapsed_seconds: float) -> float:
    """Use the same manual-vs-automated assumption everywhere in the UI."""
    return max(0, (created_count * 15 - elapsed_seconds / 60) / 60)


def build_campaign_summary_cards(
    total_assets: int,
    created_count: int,
    hero_reused_count: int,
    failed_count: int,
    elapsed_seconds: float,
    time_saved_hours: float,
    created_sub: str,
) -> list[dict]:
    """Build the standard summary cards used for pipeline and sample runs."""
    return [
        {
            "label": "Total Assets",
            "value": str(total_assets),
            "sub": "creatives planned",
            "icon": "📁",
            "bar_pct": 100,
        },
        {
            "label": "Created",
            "value": str(created_count),
            "sub": created_sub,
            "icon": "✅",
            "bar_pct": created_count / max(total_assets, 1) * 100,
        },
        {
            "label": "Heroes Reused",
            "value": str(hero_reused_count),
            "sub": "cached images",
            "icon": "♻️",
        },
        {
            "label": "Failed",
            "value": str(failed_count),
            "sub": "need attention",
            "icon": "⚠️",
        },
        {
            "label": "Duration",
            "value": f"{elapsed_seconds:.1f}s",
            "sub": "total pipeline time",
            "icon": "⏱️",
        },
        {
            "label": "Time Saved",
            "value": f"{time_saved_hours:.1f}h",
            "sub": "vs. manual workflow",
            "icon": "🚀",
        },
    ]
