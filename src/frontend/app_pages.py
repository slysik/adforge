"""
Page-level and section-level renderers for the AdForge Streamlit app.
"""

from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

from src.backend.analytics import build_performance_report
from src.frontend.app_components import (
    COMPLIANCE_EMOJI,
    DEFAULT_BUILDER_PRODUCTS,
    TEMPLATE_INFO,
    build_campaign_summary_cards,
    estimate_time_saved_hours,
    load_sample_report,
    render_ab_comparison,
    render_metric_cards,
    render_section_title,
)
from src.backend.models import CampaignBrief
from src.backend.templates import LayoutTemplate

ROOT = Path(__file__).resolve().parent.parent.parent
BUILDER_LANGUAGE_OPTIONS = ["en", "es", "fr", "de", "pt", "ja", "zh", "ko"]
BUILDER_FONT_OPTIONS = ["Georgia", "Helvetica", "Arial", "Times"]
DEFAULT_ASPECT_RATIOS = [
    {
        "name": "instagram_square",
        "ratio": "1:1",
        "width": 1080,
        "height": 1080,
    },
    {
        "name": "stories",
        "ratio": "9:16",
        "width": 1080,
        "height": 1920,
    },
    {
        "name": "facebook_landscape",
        "ratio": "16:9",
        "width": 1920,
        "height": 1080,
    },
]


# ---------------------------------------------------------------------------
# Brief builder
# ---------------------------------------------------------------------------


def _render_campaign_tab() -> None:
    """Collect campaign-level inputs in session state."""
    col1, col2 = st.columns(2)
    with col1:
        st.session_state.bb_name = st.text_input(
            "Campaign Name",
            value=st.session_state.get("bb_name", "My Campaign 2025"),
        )
        st.session_state.bb_brand = st.text_input(
            "Brand Name",
            value=st.session_state.get("bb_brand", "Blue Beach House Designs"),
        )
        st.session_state.bb_msg = st.text_area(
            "Campaign Message",
            value=st.session_state.get(
                "bb_msg", "Handcrafted coastal elegance for your home"
            ),
            height=80,
        )
        st.session_state.bb_tagline = st.text_input(
            "Tagline (optional)",
            value=st.session_state.get("bb_tagline", ""),
        )
    with col2:
        st.session_state.bb_region = st.text_input(
            "Target Region",
            value=st.session_state.get(
                "bb_region", "Southern Florida — Naples & Palm Beach"
            ),
        )
        st.session_state.bb_audience = st.text_input(
            "Target Audience",
            value=st.session_state.get(
                "bb_audience",
                "Home decor designers, interior stylists, ages 30-60",
            ),
        )
        st.session_state.bb_theme = st.text_input(
            "Theme",
            value=st.session_state.get("bb_theme", "warm coastal"),
        )
        st.session_state.bb_langs = st.multiselect(
            "Languages",
            BUILDER_LANGUAGE_OPTIONS,
            default=st.session_state.get("bb_langs", ["en"]),
        )

    _render_import_section()


def _render_brand_tab() -> None:
    """Collect brand guidelines and show the live palette preview."""
    gc1, gc2, gc3 = st.columns(3)
    with gc1:
        st.session_state.bb_c1 = st.color_picker(
            "Primary Color", st.session_state.get("bb_c1", "#1B4F72")
        )
        st.session_state.bb_c2 = st.color_picker(
            "Secondary Color", st.session_state.get("bb_c2", "#F5E6CA")
        )
    with gc2:
        st.session_state.bb_c3 = st.color_picker(
            "Tertiary Color", st.session_state.get("bb_c3", "#FFFFFF")
        )
        st.session_state.bb_accent = st.color_picker(
            "Accent Color", st.session_state.get("bb_accent", "#D4A574")
        )
    with gc3:
        st.session_state.bb_font = st.selectbox(
            "Font Family",
            BUILDER_FONT_OPTIONS,
            index=BUILDER_FONT_OPTIONS.index(
                st.session_state.get("bb_font", "Georgia")
            ),
        )
        st.session_state.bb_prohibited = st.text_input(
            "Prohibited Words (comma-separated)",
            value=st.session_state.get("bb_prohibited", "cheap, fake, plastic"),
        )

    colors = [
        st.session_state.bb_c1,
        st.session_state.bb_c2,
        st.session_state.bb_c3,
        st.session_state.bb_accent,
    ]
    labels = ["Primary", "Secondary", "Tertiary", "Accent"]
    swatch_items = "".join(
        f'<div style="text-align:center">'
        f'<div class="af-swatch" style="background:{color};"></div>'
        f'<div style="font-size:.65rem;margin-top:.2rem;color:#7F8C8D">{label}</div>'
        f"</div>"
        for color, label in zip(colors, labels)
    )
    st.markdown(
        f'<div class="af-swatches">{swatch_items}</div>',
        unsafe_allow_html=True,
    )

    st.session_state.bb_disclaimer = st.text_input(
        "Legal Disclaimer (optional)",
        value=st.session_state.get("bb_disclaimer", ""),
    )


def _default_product(index: int) -> dict:
    """Return a seeded product for the builder, or a generic fallback."""
    if index < len(DEFAULT_BUILDER_PRODUCTS):
        return DEFAULT_BUILDER_PRODUCTS[index]
    return {
        "id": f"product-{index + 1}",
        "name": f"Product {index + 1}",
        "description": "A beautiful handcrafted coastal product",
        "keywords": "handcrafted, coastal, design",
    }


def _render_products_tab() -> None:
    """Collect the per-product fields used by the pipeline."""
    num_products = st.number_input(
        "Number of Products",
        min_value=2,
        max_value=10,
        value=st.session_state.get("bb_nprods", 3),
        key="bb_nprods",
    )

    products_data = []
    for index in range(int(num_products)):
        default_product = _default_product(index)
        with st.expander(f"📦 Product {index + 1}", expanded=(index < 2)):
            pc1, pc2 = st.columns(2)
            with pc1:
                product_name = st.text_input(
                    "Product Name",
                    value=st.session_state.get(
                        f"bb_pname_{index}", default_product["name"]
                    ),
                    key=f"bb_pname_{index}",
                )
                product_id = st.text_input(
                    "Product ID (lowercase, hyphens)",
                    value=st.session_state.get(
                        f"bb_pid_{index}", default_product["id"]
                    ),
                    key=f"bb_pid_{index}",
                )
            with pc2:
                product_description = st.text_area(
                    "Description",
                    value=st.session_state.get(
                        f"bb_pdesc_{index}", default_product["description"]
                    ),
                    key=f"bb_pdesc_{index}",
                    height=68,
                )
                product_keywords = st.text_input(
                    "Keywords (comma-separated)",
                    value=st.session_state.get(
                        f"bb_pkw_{index}", default_product["keywords"]
                    ),
                    key=f"bb_pkw_{index}",
                )

            product_entry = {
                "id": product_id.strip(),
                "name": product_name.strip(),
                "description": product_description.strip(),
                "keywords": [
                    keyword.strip()
                    for keyword in product_keywords.split(",")
                    if keyword.strip()
                ],
            }
            if default_product.get("hero_image"):
                product_entry["hero_image"] = default_product["hero_image"]
            products_data.append(product_entry)

    st.session_state.bb_products_data = products_data


def _builder_logo_path() -> str | None:
    """Use the standard demo logo when it exists on disk."""
    logo_path = Path("data/input_assets/logo.png")
    return str(logo_path) if logo_path.exists() else None


def _build_campaign_brief() -> CampaignBrief:
    """Assemble the current builder state into the single pipeline input model."""
    return CampaignBrief(
        name=st.session_state.get("bb_name", "My Campaign"),
        brand=st.session_state.get("bb_brand", "Brand"),
        message=st.session_state.get("bb_msg", ""),
        tagline=st.session_state.get("bb_tagline") or None,
        target_region=st.session_state.get("bb_region", ""),
        target_audience=st.session_state.get("bb_audience", ""),
        theme=st.session_state.get("bb_theme") or None,
        languages=st.session_state.get("bb_langs", ["en"]),
        brand_guidelines={
            "primary_colors": [
                st.session_state.get("bb_c1", "#1B4F72").upper(),
                st.session_state.get("bb_c2", "#F5E6CA").upper(),
                st.session_state.get("bb_c3", "#FFFFFF").upper(),
            ],
            "accent_color": st.session_state.get("bb_accent", "#D4A574").upper(),
            "font_family": st.session_state.get("bb_font", "Georgia"),
            "logo_path": _builder_logo_path(),
            "prohibited_words": [
                word.strip()
                for word in st.session_state.get("bb_prohibited", "").split(",")
                if word.strip()
            ],
            "required_disclaimer": st.session_state.get("bb_disclaimer") or None,
        },
        products=st.session_state.get("bb_products_data", []),
        aspect_ratios=DEFAULT_ASPECT_RATIOS,
    )


def _render_brief_summary(brief: CampaignBrief) -> None:
    """Show the exact object the pipeline will consume before execution."""
    rows = "".join(
        f'<div><div class="af-brief-label">{label}</div><div class="af-brief-value">{value}</div></div>'
        for label, value in [
            ("Brand", brief.brand),
            ("Campaign", brief.name),
            ("Message", brief.message),
            ("Region", brief.target_region),
            ("Audience", brief.target_audience),
            ("Theme", brief.theme or "—"),
            ("Products", str(len(brief.products))),
        ]
    )
    st.markdown(
        f'<div class="af-card"><div class="af-brief-grid">{rows}</div></div>',
        unsafe_allow_html=True,
    )

    total_creatives = (
        len(brief.products) * len(brief.aspect_ratios) * len(brief.languages)
    )
    st.success(
        f"Ready to generate **{total_creatives} creatives** — "
        f"{len(brief.aspect_ratios)} ratios × {len(brief.products)} products × {len(brief.languages)} language(s)"
    )


def _render_run_controls() -> None:
    """Capture the runtime knobs without mixing them into brief validation."""
    st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
    action_col, options_col, template_col = st.columns([0.9, 1.1, 1.1])

    with action_col:
        st.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
        run_pipeline_now = st.button(
            "🚀 Run Pipeline",
            type="primary",
            use_container_width=True,
            key="main_run_pipeline",
        )

    with options_col:
        st.selectbox(
            "Image Provider",
            ["mock", "gemini", "firefly", "dalle", "auto"],
            help="Mock = no API key. Gemini = Imagen 4.0. Firefly = Adobe Firefly Services.",
            key="main_provider_choice",
        )

    with template_col:
        template_options = ["auto"] + [
            template.value for template in LayoutTemplate
        ]
        template_choice = st.selectbox(
            "Layout Template",
            template_options,
            help="Auto picks the best template per product.",
            key="main_template_choice",
        )
        if template_choice != "auto":
            info = TEMPLATE_INFO.get(LayoutTemplate(template_choice), {})
            st.caption(f"{info.get('icon', '')} {info.get('desc', '')}")

    if run_pipeline_now:
        st.session_state._run_triggered = True
        st.session_state._pipeline_reran = False


def _list_saved_briefs() -> list[Path]:
    """Return all YAML files in sample_briefs/, sorted by name."""
    briefs_dir = ROOT / "data" / "sample_briefs"
    if not briefs_dir.exists():
        return []
    return sorted(briefs_dir.glob("*.yaml"))


def _populate_builder_from_brief(brief: CampaignBrief) -> None:
    """Push a CampaignBrief's values into the bb_* session state keys."""
    st.session_state.bb_name = brief.name
    st.session_state.bb_brand = brief.brand
    st.session_state.bb_msg = brief.message
    st.session_state.bb_tagline = brief.tagline or ""
    st.session_state.bb_region = brief.target_region
    st.session_state.bb_audience = brief.target_audience
    st.session_state.bb_theme = brief.theme or ""
    st.session_state.bb_langs = brief.languages

    bg = brief.brand_guidelines
    colors = bg.primary_colors + ["#FFFFFF"] * 3  # pad if fewer than 3
    st.session_state.bb_c1 = colors[0]
    st.session_state.bb_c2 = colors[1]
    st.session_state.bb_c3 = colors[2]
    st.session_state.bb_accent = bg.accent_color or "#D4A574"
    st.session_state.bb_font = bg.font_family if bg.font_family in BUILDER_FONT_OPTIONS else "Georgia"
    st.session_state.bb_prohibited = ", ".join(bg.prohibited_words)
    st.session_state.bb_disclaimer = bg.required_disclaimer or ""

    st.session_state.bb_nprods = len(brief.products)
    for i, product in enumerate(brief.products):
        st.session_state[f"bb_pname_{i}"] = product.name
        st.session_state[f"bb_pid_{i}"] = product.id
        st.session_state[f"bb_pdesc_{i}"] = product.description
        st.session_state[f"bb_pkw_{i}"] = ", ".join(product.keywords)


def _render_import_section() -> None:
    """Render the brief import controls: file uploader + saved brief picker."""
    import yaml as _yaml

    with st.expander("📂 Import a Campaign Brief", expanded=False):
        col_upload, col_saved = st.columns(2)

        with col_upload:
            uploaded = st.file_uploader(
                "Upload YAML file",
                type=["yaml", "yml"],
                key="brief_uploader",
            )
            if uploaded is not None:
                try:
                    data = _yaml.safe_load(uploaded.read())
                    if "campaign" in data:
                        data = data["campaign"]
                    brief = CampaignBrief(**data)
                    _populate_builder_from_brief(brief)
                    st.success(f"Loaded **{brief.name}** — fields updated below.")
                    st.rerun()
                except Exception as exc:
                    st.error(f"Failed to load brief: {exc}")

        with col_saved:
            saved_briefs = _list_saved_briefs()
            if saved_briefs:
                labels = {p.stem.replace("_", " ").title(): p for p in saved_briefs}
                choice = st.selectbox(
                    "Or load a saved brief",
                    ["— Select —"] + list(labels.keys()),
                    key="saved_brief_picker",
                )
                if choice != "— Select —" and st.button("Load", key="load_saved_brief"):
                    try:
                        data = _yaml.safe_load(labels[choice].read_text())
                        if "campaign" in data:
                            data = data["campaign"]
                        brief = CampaignBrief(**data)
                        _populate_builder_from_brief(brief)
                        st.success(f"Loaded **{brief.name}**")
                        st.rerun()
                    except Exception as exc:
                        st.error(f"Failed to load brief: {exc}")
            else:
                st.caption("No saved briefs yet. Run the pipeline to save one.")


def render_brief_builder() -> CampaignBrief | None:
    """Collect input tab-by-tab, then return one validated CampaignBrief."""
    tab1, tab2, tab3, tab4 = st.tabs(["Campaign", "Brand", "Products", "Review & Run"])

    with tab1:
        _render_campaign_tab()

    with tab2:
        _render_brand_tab()

    with tab3:
        _render_products_tab()

    with tab4:
        col1, col2 = st.columns(2)
        try:
            brief = _build_campaign_brief()
        except Exception as exc:
            st.warning(f"Brief validation: {exc}")
            return None

        _render_brief_summary(brief)
        _render_run_controls()
        return brief


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


def render_analysis(analysis_data: dict):
    score = analysis_data.get("score", {})
    overall = score.get("overall", 0)
    grade = (
        "A+"
        if overall >= 95
        else "A"
        if overall >= 85
        else "B"
        if overall >= 75
        else "C"
        if overall >= 65
        else "D"
    )

    render_metric_cards(
        [
            {
                "label": "Overall Score",
                "value": f"{overall}/100",
                "sub": f"Grade {grade}",
                "icon": "🎯",
                "bar_pct": overall,
            },
            {
                "label": "Completeness",
                "value": f"{score.get('completeness', 0)}/25",
                "sub": "Brief coverage",
                "icon": "📋",
                "bar_pct": score.get("completeness", 0) * 4,
            },
            {
                "label": "Clarity",
                "value": f"{score.get('clarity', 0)}/25",
                "sub": "Message clarity",
                "icon": "💡",
                "bar_pct": score.get("clarity", 0) * 4,
            },
            {
                "label": "Brand Strength",
                "value": f"{score.get('brand_strength', 0)}/25",
                "sub": "Brand consistency",
                "icon": "🏷️",
                "bar_pct": score.get("brand_strength", 0) * 4,
            },
            {
                "label": "Targeting",
                "value": f"{score.get('targeting', 0)}/25",
                "sub": "Audience fit",
                "icon": "🎯",
                "bar_pct": score.get("targeting", 0) * 4,
            },
        ]
    )

    if analysis_data.get("strengths") or analysis_data.get("weaknesses"):
        with st.expander("📊 Brief Insights", expanded=True):
            col1, col2 = st.columns(2)
            with col1:
                if analysis_data.get("strengths"):
                    render_section_title("Strengths")
                    for s in analysis_data["strengths"]:
                        st.markdown(f"✅ {s}")
            with col2:
                if analysis_data.get("weaknesses"):
                    render_section_title("Improvements")
                    for w in analysis_data["weaknesses"]:
                        st.markdown(f"💡 {w}")


# ---------------------------------------------------------------------------
# Approval queue
# ---------------------------------------------------------------------------


def render_approval_queue(assets: list[dict], session_key: str = "default"):
    if not assets:
        st.info("No assets to review.")
        return

    state_key = f"approvals_{session_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            i: {"status": "pending", "comment": ""} for i in range(len(assets))
        }
    approvals = st.session_state[state_key]

    statuses = [approvals[i]["status"] for i in range(len(assets))]
    approved = statuses.count("approved")
    rejected = statuses.count("rejected")
    pending = statuses.count("pending")
    total = len(assets)
    pct_done = ((approved + rejected) / total * 100) if total else 0

    STATUS_COLORS = {
        "pending": {
            "bg": "#FEF3E2",
            "border": "#E8B849",
            "text": "#8B6914",
            "badge": "#F4D03F",
            "icon": "⏳",
        },
        "approved": {
            "bg": "#E8F5E9",
            "border": "#4CAF50",
            "text": "#2E7D32",
            "badge": "#66BB6A",
            "icon": "✅",
        },
        "rejected": {
            "bg": "#FFEBEE",
            "border": "#EF5350",
            "text": "#C62828",
            "badge": "#EF5350",
            "icon": "❌",
        },
    }

    # --- Progress bar + summary strip ---
    approved_pct = approved / total * 100 if total else 0
    rejected_pct = rejected / total * 100 if total else 0
    pending_pct = pending / total * 100 if total else 0
    st.markdown(
        f"""
    <div style="background:var(--warm-ivory);border:1px solid var(--sandy-beige);border-radius:var(--radius-md);
                padding:1rem 1.2rem;margin-bottom:1rem">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;flex-wrap:wrap;gap:0.5rem">
        <div style="font-size:1.05rem;font-weight:700;color:var(--charcoal)">
          Review Progress — <span style="color:var(--ocean-blue)">{pct_done:.0f}%</span> complete
        </div>
        <div style="display:flex;gap:1rem;font-size:0.88rem">
          <span style="color:{STATUS_COLORS["pending"]["text"]}">⏳ {pending} pending</span>
          <span style="color:{STATUS_COLORS["approved"]["text"]}">✅ {approved} approved</span>
          <span style="color:{STATUS_COLORS["rejected"]["text"]}">❌ {rejected} rejected</span>
        </div>
      </div>
      <div style="height:8px;border-radius:4px;background:#E0D5C7;overflow:hidden;display:flex">
        <div style="width:{approved_pct}%;background:#4CAF50;transition:width 0.3s"></div>
        <div style="width:{rejected_pct}%;background:#EF5350;transition:width 0.3s"></div>
        <div style="width:{pending_pct}%;background:#F4D03F;transition:width 0.3s"></div>
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # --- Bulk action buttons ---
    b1, b2, b3, spacer = st.columns([1, 1, 1, 3])
    if b1.button(
        "✅ Approve All", key=f"approve_all_{session_key}", use_container_width=True
    ):
        for i in range(len(assets)):
            approvals[i]["status"] = "approved"
        st.rerun()
    if b2.button(
        "❌ Reject All", key=f"reject_all_{session_key}", use_container_width=True
    ):
        for i in range(len(assets)):
            approvals[i]["status"] = "rejected"
        st.rerun()
    if b3.button(
        "🔄 Reset All", key=f"reset_all_{session_key}", use_container_width=True
    ):
        for i in range(len(assets)):
            approvals[i]["status"] = "pending"
            approvals[i]["comment"] = ""
        st.rerun()

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # --- Per-asset review cards (rows of 3) ---
    for row_start in range(0, len(assets), 3):
        row_assets = list(enumerate(assets))[row_start : row_start + 3]
        cols = st.columns(3)
        for col, (i, asset) in zip(cols, row_assets):
            pid = asset.get("product_id", "unknown")
            ratio = asset.get("aspect_ratio", "?")
            lang = asset.get("language", "?")
            status = approvals[i]["status"]
            sc = STATUS_COLORS[status]

            brand = asset.get("brand_compliance", {}).get("status", "not_checked")
            legal = asset.get("legal_compliance", {}).get("status", "not_checked")
            hero = asset.get("hero_status", "generated")

            product_name = pid.replace("-", " ").title()

            with col:
                st.markdown(
                    f"""
                <div style="background:{sc["bg"]};border-left:4px solid {sc["border"]};
                            border-radius:var(--radius-sm);padding:0.7rem 0.8rem;margin-bottom:0.4rem;
                            box-shadow:var(--shadow-sm)">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem">
                    <span style="font-size:0.92rem;font-weight:700;color:var(--charcoal)">{product_name}</span>
                    <span style="background:{sc["badge"]};color:#fff;padding:2px 8px;border-radius:10px;
                                 font-size:0.75rem;font-weight:600;text-transform:uppercase">
                      {sc["icon"]} {status}
                    </span>
                  </div>
                  <div style="font-size:0.82rem;color:var(--charcoal-mid);margin-bottom:0.2rem">
                    {ratio} · {lang.upper()}
                    <span style="margin-left:0.5rem">
                      {COMPLIANCE_EMOJI.get(brand, "—")} Brand
                      {COMPLIANCE_EMOJI.get(legal, "—")} Legal
                    </span>
                  </div>
                  <div style="font-size:0.78rem;color:var(--charcoal-light)">
                    {"♻️ Reused hero" if hero == "reused" else "✦ AI-generated hero"}
                  </div>
                </div>
                """,
                    unsafe_allow_html=True,
                )

                fp = asset.get("file_path", "")
                if fp and Path(fp).exists():
                    st.image(fp, use_container_width=True)
                else:
                    st.warning("Image not available")

                new_status = st.radio(
                    "Decision",
                    ["pending", "approved", "rejected"],
                    index=["pending", "approved", "rejected"].index(status),
                    key=f"status_{session_key}_{i}",
                    horizontal=True,
                    label_visibility="collapsed",
                )
                if new_status != status:
                    approvals[i]["status"] = new_status

                approvals[i]["comment"] = st.text_input(
                    "Note",
                    value=approvals[i]["comment"],
                    key=f"comment_{session_key}_{i}",
                    placeholder="Add reviewer note…",
                    label_visibility="collapsed",
                )

                st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

    # --- Export section ---
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    exp_col1, exp_col2, _ = st.columns([1.5, 1.5, 3])
    with exp_col1:
        if st.button(
            "📋 Export Manifest",
            key=f"export_{session_key}",
            use_container_width=True,
        ):
            manifest = []
            for i, asset in enumerate(assets):
                manifest.append(
                    {
                        "product_id": asset.get("product_id"),
                        "aspect_ratio": asset.get("aspect_ratio"),
                        "language": asset.get("language"),
                        "file_path": asset.get("file_path"),
                        "approval_status": approvals[i]["status"],
                        "reviewer_comment": approvals[i]["comment"],
                    }
                )
            st.session_state[f"_manifest_{session_key}"] = manifest
    with exp_col2:
        manifest = st.session_state.get(f"_manifest_{session_key}")
        if manifest:
            st.download_button(
                "⬇ Download JSON",
                data=json.dumps(manifest, indent=2),
                file_name="approval_manifest.json",
                mime="application/json",
                key=f"download_{session_key}",
                use_container_width=True,
            )
    if st.session_state.get(f"_manifest_{session_key}"):
        st.json(st.session_state[f"_manifest_{session_key}"])


# ---------------------------------------------------------------------------
# Performance analytics
# ---------------------------------------------------------------------------


def render_performance(assets: list[dict], session_key: str = "default"):
    if not assets:
        st.info("No assets to analyze.")
        return

    perf = build_performance_report(assets)

    CARD_BG = "#FFF9F2"
    BORDER = "var(--sandy-beige)"
    SAND = "var(--shell-tan)"
    CHARCOAL = "var(--charcoal)"
    CHARCOAL_M = "var(--charcoal-mid)"
    GREEN = "#2E7D32"
    RED = "#C62828"
    GOLD_BG = "#FFF3D0"
    GOLD_BORDER = "#E8B849"
    GOLD_TEXT = "#8B6914"
    ROW_ALT = "rgba(212,165,116,0.06)"
    ROW_WINNER = "rgba(232,184,73,0.12)"

    sorted_kpis = sorted(perf.kpis, key=lambda x: x.cpa)
    winner_id = perf.winner.creative_id if perf.winner else None

    # ── Summary metric cards ──
    st.markdown(
        f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.8rem;margin-bottom:1rem">
      <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:var(--radius-sm);padding:0.8rem 1rem;text-align:center">
        <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.05em;color:{CHARCOAL_M};margin-bottom:0.2rem">Total Spend</div>
        <div style="font-size:1.3rem;font-weight:700;color:{CHARCOAL}">${perf.total_spend:,.0f}</div>
      </div>
      <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:var(--radius-sm);padding:0.8rem 1rem;text-align:center">
        <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.05em;color:{CHARCOAL_M};margin-bottom:0.2rem">Impressions</div>
        <div style="font-size:1.3rem;font-weight:700;color:{CHARCOAL}">{perf.total_impressions / 1000:.1f}K</div>
      </div>
      <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:var(--radius-sm);padding:0.8rem 1rem;text-align:center">
        <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.05em;color:{CHARCOAL_M};margin-bottom:0.2rem">Avg Click-Through Rate</div>
        <div style="font-size:1.3rem;font-weight:700;color:{CHARCOAL}">{perf.avg_ctr:.2f}%</div>
      </div>
      <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:var(--radius-sm);padding:0.8rem 1rem;text-align:center">
        <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.05em;color:{CHARCOAL_M};margin-bottom:0.2rem">Avg Cost Per Acquisition</div>
        <div style="font-size:1.3rem;font-weight:700;color:{CHARCOAL}">${perf.avg_cpa:.2f}</div>
      </div>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # ── Winner banner ──
    if perf.winner:
        w = perf.winner
        ctr_delta = ((w.ctr - perf.avg_ctr) / perf.avg_ctr * 100) if perf.avg_ctr else 0
        cpa_delta = ((perf.avg_cpa - w.cpa) / perf.avg_cpa * 100) if perf.avg_cpa else 0
        st.markdown(
            f"""
        <div style="background:{GOLD_BG};border-left:4px solid {GOLD_BORDER};border-radius:var(--radius-sm);
                    padding:0.8rem 1.2rem;margin-bottom:1rem;display:flex;align-items:center;gap:0.8rem;flex-wrap:wrap">
          <span style="font-size:1.4rem">🏆</span>
          <div>
            <div style="font-size:1rem;font-weight:700;color:{GOLD_TEXT}">Top Performer — {w.creative_id.replace("-", " ").title()}</div>
            <div style="font-size:0.88rem;color:{CHARCOAL_M};margin-top:0.15rem">
              Click-Through Rate <strong style="color:{CHARCOAL}">{w.ctr:.2f}%</strong>
              <span style="color:{GREEN if ctr_delta > 0 else RED};font-size:0.82rem;margin-left:0.2rem">{"+" if ctr_delta > 0 else ""}{ctr_delta:.0f}% vs avg</span>
              &nbsp;·&nbsp;
              Cost Per Acquisition <strong style="color:{CHARCOAL}">${w.cpa:.2f}</strong>
              <span style="color:{GREEN if cpa_delta > 0 else RED};font-size:0.82rem;margin-left:0.2rem">{cpa_delta:.0f}% better</span>
              &nbsp;·&nbsp;
              <strong style="color:{CHARCOAL}">{w.conversions}</strong> conversions
            </div>
          </div>
        </div>
        """,
            unsafe_allow_html=True,
        )

    # ── KPI Table ──
    table_rows = ""
    for idx, k in enumerate(sorted_kpis):
        is_winner = k.creative_id == winner_id
        bg = ROW_WINNER if is_winner else (ROW_ALT if idx % 2 == 0 else "transparent")
        badge = (
            '<span style="background:#E8B849;color:#fff;padding:1px 6px;border-radius:8px;font-size:0.72rem;margin-left:0.3rem">BEST</span>'
            if is_winner
            else ""
        )
        ctr_color = GREEN if k.ctr > perf.avg_ctr else CHARCOAL
        cpa_color = GREEN if k.cpa < perf.avg_cpa else CHARCOAL
        table_rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:0.45rem 0.6rem;font-weight:{"700" if is_winner else "400"}">{k.creative_id}{badge}</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.product_id.replace("-", " ").title()}</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.aspect_ratio}</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.language.upper()}</td>'
            f'<td style="padding:0.45rem 0.6rem">${k.spend_usd:.0f}</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.impressions:,}</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.clicks:,}</td>'
            f'<td style="padding:0.45rem 0.6rem;color:{ctr_color};font-weight:600">{k.ctr:.2f}%</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.conversions}</td>'
            f'<td style="padding:0.45rem 0.6rem;color:{cpa_color};font-weight:600">${k.cpa:.2f}</td>'
            f"</tr>"
        )

    st.markdown(
        f"""
    <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:var(--radius-sm);padding:1rem;overflow-x:auto">
      <div style="font-size:0.95rem;font-weight:700;color:{CHARCOAL};margin-bottom:0.6rem">Per-Creative Performance Indicators</div>
      <table style="width:100%;border-collapse:collapse;font-size:0.88rem;color:{CHARCOAL}">
        <thead>
          <tr style="border-bottom:2px solid {BORDER}">
            {"".join(f'<th style="padding:0.45rem 0.6rem;text-align:left;color:{SAND};font-weight:700;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.04em">{h}</th>' for h in ["Creative", "Product", "Ratio", "Lang", "Spend", "Impressions", "Clicks", "Click-Through Rate", "Conversions", "Cost Per Acq."])}
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
    """,
        unsafe_allow_html=True,
    )

    # ── Export ──
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    csv_data = [
        f"{k.creative_id},{k.product_id},{k.aspect_ratio},{k.language},{k.spend_usd:.2f},{k.impressions},{k.clicks},{k.conversions},{k.ctr:.2f},{k.cpa:.2f},{k.cpc:.2f}"
        for k in perf.kpis
    ]
    csv_header = "creative_id,product_id,aspect_ratio,language,spend_usd,impressions,clicks,conversions,click_through_rate_pct,cost_per_acquisition_usd,cost_per_click_usd"
    dl_col, _ = st.columns([1.5, 4.5])
    with dl_col:
        st.download_button(
            "⬇ Download KPIs (CSV)",
            data=csv_header + "\n" + "\n".join(csv_data),
            file_name="creative_kpis.csv",
            mime="text/csv",
            key=f"download_kpis_{session_key}",
            use_container_width=True,
        )
    st.caption("*Sample data for demo purposes.*")


def render_metrics(report: dict):
    metrics = report.get("metrics")
    if not metrics:
        st.info("No metrics available for this run.")
        return

    stages = metrics.get("stages", [])
    if stages:
        render_section_title("Stage Breakdown")
        cards = []
        for stage in stages:
            name = stage.get("name", "unknown")
            elapsed_s = stage.get("elapsed_ms", 0) / 1000.0
            items = stage.get("items_processed", 0)
            api_calls = stage.get("api_calls", 0)
            cost = stage.get("estimated_cost_usd", 0)
            cards.append(
                {
                    "label": name,
                    "value": f"{elapsed_s:.2f}s",
                    "sub": f"{items} items · {api_calls} API calls · {'${:.3f}'.format(cost) if cost else 'no cost'}",
                    "icon": "⚙️",
                }
            )
        render_metric_cards(cards)

    provider = metrics.get("provider", metrics.get("provider_used", "unknown"))
    st.markdown(f"**Provider:** `{provider}`")


def serialize_result_assets(result) -> list[dict]:
    """Prepare assets for gallery and approval queue rendering."""
    assets = []
    for asset in result.assets:
        data = asset.model_dump()
        data["hero_status"] = (
            data["hero_status"].value
            if hasattr(data["hero_status"], "value")
            else data["hero_status"]
        )
        if data.get("brand_compliance") and hasattr(
            data["brand_compliance"].get("status", ""), "value"
        ):
            data["brand_compliance"]["status"] = data["brand_compliance"][
                "status"
            ].value
        if data.get("legal_compliance") and hasattr(
            data["legal_compliance"].get("status", ""), "value"
        ):
            data["legal_compliance"]["status"] = data["legal_compliance"][
                "status"
            ].value
        assets.append(data)
    return assets


def render_pipeline_results(brief, result):
    """Render the post-run tabs and summary for a completed pipeline."""
    time_saved_hrs = estimate_time_saved_hours(
        result.created_count, result.elapsed_seconds
    )
    assets_data = serialize_result_assets(result)

    tab_campaign, tab_approval, tab_ab, tab_analytics = st.tabs(
        ["Campaign", "Approval", "Variations", "Analytics"]
    )

    with tab_campaign:
        render_metric_cards(
            build_campaign_summary_cards(
                total_assets=result.total_assets,
                created_count=result.created_count,
                hero_reused_count=result.hero_reused_count,
                failed_count=result.failed_count,
                elapsed_seconds=result.elapsed_seconds,
                time_saved_hours=time_saved_hrs,
                created_sub="successfully done",
            )
        )
        if result.warnings:
            with st.expander(f"⚠️ Warnings ({len(result.warnings)})"):
                for warning in result.warnings:
                    st.warning(warning)

    with tab_approval:
        render_approval_queue(assets_data, session_key="pipeline_run")

    with tab_ab:
        st.markdown(
            '<div style="color:var(--charcoal-mid);font-size:0.92rem;margin-bottom:0.5rem">'
            "Compare all 5 layout templates side-by-side using the generated hero images.</div>",
            unsafe_allow_html=True,
        )
        from src.backend.storage import StorageManager as _SM
        from src.backend.storage import slugify as _slugify

        storage = _SM(input_dir=Path("data/input_assets"), output_dir=Path("output"))
        for product in brief.products:
            st.markdown(f"**{product.name}**")
            hero_dir = storage.get_campaign_dir(brief.name) / _slugify(product.id)
            hero_candidates = list(hero_dir.rglob("hero*.png")) + list(
                hero_dir.rglob("hero*.jpg")
            )
            if hero_candidates:
                render_ab_comparison(brief, hero_candidates[0])
            else:
                st.info(f"No hero found for {product.name}")
            st.divider()

    with tab_analytics:
        render_performance(assets_data, session_key="pipeline_run")
        from src.backend.storage import StorageManager

        storage = StorageManager(
            input_dir=Path("data/input_assets"), output_dir=Path("output")
        )
        campaign_dir = storage.get_campaign_dir(brief.name)
        report = load_sample_report(campaign_dir)
        if report:
            render_metrics(report)
        else:
            st.info("Metrics available in the JSON report.")


def _slugify_filename(name: str) -> str:
    """Convert a campaign name to a filesystem-safe slug."""
    import re

    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "_", slug)
    slug = slug.strip("_")
    return slug or "campaign"


def save_generated_brief_yaml(brief) -> str:
    """Persist a built brief to sample_briefs/ so users can see and reuse it."""
    import yaml as _yaml

    briefs_dir = ROOT / "data" / "sample_briefs"
    briefs_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{_slugify_filename(brief.name)}.yaml"
    out_path = briefs_dir / filename

    brief_yaml = _yaml.dump(
        {"campaign": brief.model_dump(exclude_none=True)},
        default_flow_style=False,
    )
    out_path.write_text(brief_yaml)
    return str(out_path)
