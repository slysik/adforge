"""
AdForge Web UI — Streamlit frontend for the creative automation pipeline.

Launch with:
    streamlit run src/app.py
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

import streamlit as st

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.pipeline import load_brief, run_pipeline
from src.analyzer import analyze_brief
from src.analytics import build_performance_report, export_kpis_csv
from src.templates import LayoutTemplate, TEMPLATE_RENDERERS, auto_select_template
from src.compositor import Compositor, _hex_to_rgb

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="AdForge — Creative Automation",
    page_icon="🎨",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Run log (persists across reruns in session state)
# ---------------------------------------------------------------------------
if "run_log" not in st.session_state:
    st.session_state.run_log = []


def _log_run(
    campaign: str,
    provider: str,
    total: int,
    created: int,
    failed: int,
    elapsed: float,
    time_saved_hrs: float,
):
    """Append a pipeline run to the session-level run log."""
    from datetime import datetime
    st.session_state.run_log.insert(0, {
        "timestamp": datetime.now().strftime("%H:%M:%S"),
        "campaign": campaign,
        "provider": provider,
        "total": total,
        "created": created,
        "failed": failed,
        "elapsed": f"{elapsed:.1f}s",
        "time_saved": f"{time_saved_hrs:.1f}h",
    })


def _render_run_log():
    """Display the run history table."""
    log = st.session_state.run_log
    if not log:
        st.info("No pipeline runs yet this session. Run a pipeline to see history here.")
        return
    st.dataframe(log, use_container_width=True, hide_index=True)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_BRIEFS = {
    "Coastal Collection 2025 (Blue Beach House Designs)": "sample_briefs/beach_house_campaign.yaml",
    "Summer Refresh 2025 (FreshCo)": "sample_briefs/summer_campaign.yaml",
    "Holiday Glow 2025 (LuxeBeauty)": "sample_briefs/holiday_campaign.yaml",
}

COMPLIANCE_EMOJI = {
    "passed": "✅",
    "warning": "⚠️",
    "failed": "❌",
    "not_checked": "—",
}

# Template metadata for UI display
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


def _render_ab_comparison(brief, sample_hero_path: Path | None = None):
    """Render A/B template comparison for a product using all 5 templates.

    Generates quick previews by compositing the same hero image with each
    template layout, allowing creatives to compare side-by-side before
    committing to a full pipeline run.
    """
    from PIL import Image as PILImage

    if sample_hero_path is None or not sample_hero_path.exists():
        st.info("No hero image available for A/B preview. Run the pipeline first or provide a hero asset.")
        return

    hero = PILImage.open(str(sample_hero_path)).convert("RGBA")
    bg = brief.brand_guidelines

    # Use first aspect ratio for preview
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
                st.image(canvas.convert("RGB"), caption=f"{info['icon']} {info['label']}", use_container_width=True)
            except Exception as e:
                st.error(f"{info['label']}: {e}")

        # Show auto-select indicator
        auto = auto_select_template(ratio.ratio, brief.products[0].keywords, brief.message)
        if template == auto:
            with col:
                st.success("Auto-selected")


def _render_brief_builder():
    """Render an interactive campaign brief builder form.

    Returns a CampaignBrief if the form is valid, or None if incomplete.
    Persists form state in Streamlit session_state so values survive reruns.
    """
    from src.models import CampaignBrief, Product, AspectRatio, BrandGuidelines

    st.markdown("### Build a Campaign Brief")
    st.caption("Fill in the form below to create a custom campaign brief without writing YAML.")

    # Basic campaign info
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Campaign Name", value="My Campaign 2025", key="bb_name")
        brand = st.text_input("Brand Name", value="Blue Beach House Designs", key="bb_brand")
        message = st.text_area("Campaign Message", value="Handcrafted coastal elegance for your home", key="bb_msg", height=80)
        tagline = st.text_input("Tagline (optional)", value="", key="bb_tagline")
    with col2:
        region = st.text_input("Target Region", value="Southern Florida — Naples & Palm Beach", key="bb_region")
        audience = st.text_input("Target Audience", value="Home decor designers, interior stylists, ages 30-60", key="bb_audience")
        languages = st.multiselect("Languages", ["en", "es", "fr", "de", "pt", "ja", "zh", "ko"], default=["en"], key="bb_langs")

    # Brand guidelines
    st.markdown("#### Brand Guidelines")
    gc1, gc2, gc3 = st.columns(3)
    with gc1:
        color1 = st.color_picker("Primary Color", "#1B4F72", key="bb_c1")
        color2 = st.color_picker("Secondary Color", "#F5E6CA", key="bb_c2")
    with gc2:
        color3 = st.color_picker("Tertiary Color", "#FFFFFF", key="bb_c3")
        accent = st.color_picker("Accent Color", "#D4A574", key="bb_accent")
    with gc3:
        font = st.selectbox("Font Family", ["Georgia", "Helvetica", "Arial", "Times"], key="bb_font")
        prohibited = st.text_input("Prohibited Words (comma-separated)", value="cheap, fake, plastic", key="bb_prohibited")

    disclaimer = st.text_input("Legal Disclaimer (optional)", value="", key="bb_disclaimer")

    # Products (at least 2)
    st.markdown("#### Products")
    num_products = st.number_input("Number of Products", min_value=2, max_value=10, value=2, key="bb_nprods")

    products_data = []
    for i in range(int(num_products)):
        with st.expander(f"Product {i + 1}", expanded=(i < 2)):
            pc1, pc2 = st.columns(2)
            with pc1:
                p_name = st.text_input("Product Name", value=f"Product {i + 1}", key=f"bb_pname_{i}")
                p_id = st.text_input("Product ID (lowercase, hyphens)", value=f"product-{i + 1}", key=f"bb_pid_{i}")
            with pc2:
                p_desc = st.text_area("Description", value="A beautiful handcrafted product", key=f"bb_pdesc_{i}", height=68)
                p_kw = st.text_input("Keywords (comma-separated)", value="handcrafted, coastal, design", key=f"bb_pkw_{i}")

            products_data.append({
                "id": p_id.strip(),
                "name": p_name.strip(),
                "description": p_desc.strip(),
                "keywords": [k.strip() for k in p_kw.split(",") if k.strip()],
            })

    # Aspect ratios
    st.markdown("#### Aspect Ratios")
    default_ratios = [
        {"name": "instagram_square", "ratio": "1:1", "width": 1080, "height": 1080},
        {"name": "stories", "ratio": "9:16", "width": 1080, "height": 1920},
        {"name": "facebook_landscape", "ratio": "16:9", "width": 1920, "height": 1080},
    ]
    use_defaults = st.checkbox("Use standard ratios (1:1, 9:16, 16:9)", value=True, key="bb_default_ratios")

    # Build brief dict
    brief_dict = {
        "name": name,
        "brand": brand,
        "message": message,
        "tagline": tagline or None,
        "target_region": region,
        "target_audience": audience,
        "languages": languages,
        "brand_guidelines": {
            "primary_colors": [color1.upper(), color2.upper(), color3.upper()],
            "accent_color": accent.upper(),
            "font_family": font,
            "prohibited_words": [w.strip() for w in prohibited.split(",") if w.strip()],
            "required_disclaimer": disclaimer or None,
        },
        "products": products_data,
    }
    if use_defaults:
        brief_dict["aspect_ratios"] = default_ratios

    # Validate and return
    try:
        brief = CampaignBrief(**brief_dict)
        return brief
    except Exception as e:
        st.warning(f"Brief validation: {e}")
        return None


def _load_sample_report(campaign_dir: Path) -> dict | None:
    """Load a pre-generated report.json from a campaign directory."""
    report_path = campaign_dir / "report.json"
    if report_path.exists():
        return json.loads(report_path.read_text())
    return None


def _find_sample_campaigns(base: Path) -> list[Path]:
    """Find campaign directories in sample_output/."""
    if not base.exists():
        return []
    return sorted([d for d in base.iterdir() if d.is_dir() and (d / "report.json").exists()])


def _render_gallery(assets: list[dict], base_dir: Path | None = None):
    """Render a creative gallery grouped by product, showing ratios side-by-side."""
    products = {}
    for asset in assets:
        pid = asset["product_id"]
        if pid not in products:
            products[pid] = []
        products[pid].append(asset)

    for product_id, product_assets in products.items():
        st.subheader(f"📦 {product_id}")

        languages = sorted(set(a["language"] for a in product_assets))

        for lang in languages:
            lang_assets = [a for a in product_assets if a["language"] == lang]
            lang_assets.sort(key=lambda a: a["aspect_ratio"])

            st.markdown(f"**Language: `{lang.upper()}`**")
            cols = st.columns(len(lang_assets))

            for col, asset in zip(cols, lang_assets):
                file_path = asset["file_path"]
                if base_dir and not Path(file_path).is_absolute():
                    file_path = str(base_dir / Path(file_path).relative_to(
                        Path(file_path).parts[0]
                    )) if Path(file_path).parts else file_path

                with col:
                    st.caption(f"**{asset['aspect_ratio']}**")
                    if Path(file_path).exists():
                        st.image(str(file_path), use_container_width=True)
                    else:
                        st.warning(f"File not found: {file_path}")

                    brand = asset.get("brand_compliance", {}).get("status", "not_checked")
                    legal = asset.get("legal_compliance", {}).get("status", "not_checked")
                    hero = asset.get("hero_status", "generated")
                    hero_icon = "♻️" if hero == "reused" else "✦"

                    st.caption(
                        f"Brand {COMPLIANCE_EMOJI.get(brand, '—')} · "
                        f"Legal {COMPLIANCE_EMOJI.get(legal, '—')} · "
                        f"Hero {hero_icon}"
                    )

        st.divider()


def _render_analysis(analysis_data: dict):
    """Render brief analysis from report JSON (key: brief_analysis)."""
    score = analysis_data.get("score", {})
    overall = score.get("overall", 0)

    grade = "A+" if overall >= 95 else "A" if overall >= 85 else "B" if overall >= 75 else "C" if overall >= 65 else "D"
    st.progress(overall / 100, text=f"Brief Quality: {overall}/100 ({grade})")

    sc1, sc2, sc3, sc4 = st.columns(4)
    sc1.metric("Completeness", f"{score.get('completeness', 0)}/25")
    sc2.metric("Clarity", f"{score.get('clarity', 0)}/25")
    sc3.metric("Brand Strength", f"{score.get('brand_strength', 0)}/25")
    sc4.metric("Targeting", f"{score.get('targeting', 0)}/25")

    if analysis_data.get("strengths"):
        st.markdown("**Strengths:**")
        for s in analysis_data["strengths"]:
            st.markdown(f"- ✅ {s}")

    if analysis_data.get("weaknesses"):
        st.markdown("**Improvements:**")
        for w in analysis_data["weaknesses"]:
            st.markdown(f"- 💡 {w}")


def _render_approval_queue(assets: list[dict], session_key: str = "default"):
    """Render an approval queue for reviewing generated creatives."""
    if not assets:
        st.info("No assets to review.")
        return

    # Initialize session state for approvals
    state_key = f"approvals_{session_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            i: {"status": "pending", "comment": ""}
            for i in range(len(assets))
        }
    approvals = st.session_state[state_key]

    # Summary counts
    statuses = [approvals[i]["status"] for i in range(len(assets))]
    approved = statuses.count("approved")
    rejected = statuses.count("rejected")
    pending = statuses.count("pending")

    c1, c2, c3 = st.columns(3)
    c1.metric("Pending", pending)
    c2.metric("Approved", approved)
    c3.metric("Rejected", rejected)

    # Bulk actions
    col_a, col_r, col_reset = st.columns(3)
    if col_a.button("Approve All", key=f"approve_all_{session_key}"):
        for i in range(len(assets)):
            approvals[i]["status"] = "approved"
        st.rerun()
    if col_r.button("Reject All", key=f"reject_all_{session_key}"):
        for i in range(len(assets)):
            approvals[i]["status"] = "rejected"
        st.rerun()
    if col_reset.button("Reset All", key=f"reset_all_{session_key}"):
        for i in range(len(assets)):
            approvals[i]["status"] = "pending"
            approvals[i]["comment"] = ""
        st.rerun()

    st.divider()

    # Per-asset review
    for i, asset in enumerate(assets):
        pid = asset.get("product_id", "unknown")
        ratio = asset.get("aspect_ratio", "?")
        lang = asset.get("language", "?")
        status = approvals[i]["status"]
        status_icon = {"pending": "⏳", "approved": "✅", "rejected": "❌"}[status]

        with st.expander(f"{status_icon} {pid} / {ratio} / {lang}", expanded=(status == "pending")):
            img_col, ctrl_col = st.columns([2, 1])
            with img_col:
                fp = asset.get("file_path", "")
                if fp and Path(fp).exists():
                    st.image(fp, use_container_width=True)
                else:
                    st.warning("Image not available")

            with ctrl_col:
                brand = asset.get("brand_compliance", {}).get("status", "not_checked")
                legal = asset.get("legal_compliance", {}).get("status", "not_checked")
                st.markdown(f"**Brand:** {COMPLIANCE_EMOJI.get(brand, '—')} {brand}")
                st.markdown(f"**Legal:** {COMPLIANCE_EMOJI.get(legal, '—')} {legal}")
                hero = asset.get("hero_status", "generated")
                st.markdown(f"**Hero:** {'♻️ reused' if hero == 'reused' else '✦ generated'}")

                new_status = st.radio(
                    "Decision",
                    ["pending", "approved", "rejected"],
                    index=["pending", "approved", "rejected"].index(status),
                    key=f"status_{session_key}_{i}",
                    horizontal=True,
                )
                if new_status != status:
                    approvals[i]["status"] = new_status

                approvals[i]["comment"] = st.text_input(
                    "Comment",
                    value=approvals[i]["comment"],
                    key=f"comment_{session_key}_{i}",
                )

    # Export manifest
    st.divider()
    if st.button("Export Approval Manifest (JSON)", key=f"export_{session_key}"):
        manifest = []
        for i, asset in enumerate(assets):
            manifest.append({
                "product_id": asset.get("product_id"),
                "aspect_ratio": asset.get("aspect_ratio"),
                "language": asset.get("language"),
                "file_path": asset.get("file_path"),
                "approval_status": approvals[i]["status"],
                "reviewer_comment": approvals[i]["comment"],
            })
        st.json(manifest)
        st.download_button(
            "Download manifest.json",
            data=json.dumps(manifest, indent=2),
            file_name="approval_manifest.json",
            mime="application/json",
            key=f"download_{session_key}",
        )


def _render_performance(assets: list[dict]):
    """Render performance analytics with sample KPI data and winner detection."""
    if not assets:
        st.info("No assets to analyze.")
        return

    perf = build_performance_report(assets)

    # Summary metrics
    st.markdown("#### Campaign Performance (Sample Data)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Spend", f"${perf.total_spend:,.2f}")
    c2.metric("Impressions", f"{perf.total_impressions:,}")
    c3.metric("Avg CTR", f"{perf.avg_ctr:.2f}%")
    c4.metric("Avg CPA", f"${perf.avg_cpa:.2f}")

    # Winner callout
    if perf.winner:
        st.success(
            f"**Winner:** `{perf.winner.creative_id}` — "
            f"CTR {perf.winner.ctr:.2f}% · CPA ${perf.winner.cpa:.2f} · "
            f"{perf.winner.conversions} conversions"
        )

    # KPI table
    st.markdown("#### Per-Creative KPIs")
    table_data = []
    for k in sorted(perf.kpis, key=lambda x: x.cpa):
        is_winner = perf.winner and k.creative_id == perf.winner.creative_id
        table_data.append({
            "Creative": ("🏆 " if is_winner else "") + k.creative_id,
            "Product": k.product_id,
            "Ratio": k.aspect_ratio,
            "Lang": k.language,
            "Spend": f"${k.spend_usd:.2f}",
            "Impressions": f"{k.impressions:,}",
            "Clicks": f"{k.clicks:,}",
            "CTR %": f"{k.ctr:.2f}",
            "Conversions": k.conversions,
            "CPA": f"${k.cpa:.2f}",
        })
    st.dataframe(table_data, use_container_width=True, hide_index=True)

    # CSV export
    csv_data = []
    for k in perf.kpis:
        csv_data.append(
            f"{k.creative_id},{k.product_id},{k.aspect_ratio},{k.language},"
            f"{k.spend_usd:.2f},{k.impressions},{k.clicks},{k.conversions},"
            f"{k.ctr:.2f},{k.cpa:.2f},{k.cpc:.2f}"
        )
    csv_header = "creative_id,product_id,aspect_ratio,language,spend_usd,impressions,clicks,conversions,ctr_pct,cpa_usd,cpc_usd"
    csv_content = csv_header + "\n" + "\n".join(csv_data)
    st.download_button(
        "Download KPIs (CSV)",
        data=csv_content,
        file_name="creative_kpis.csv",
        mime="text/csv",
    )

    st.caption("*Sample data generated for demo purposes. In production, this would ingest real ad platform metrics.*")


def _render_metrics(report: dict):
    """Render pipeline metrics from report data."""
    metrics = report.get("metrics")
    if not metrics:
        st.info("No metrics available for this run.")
        return

    stages = metrics.get("stages", [])
    if stages:
        st.markdown("#### Stage Breakdown")
        for stage in stages:
            name = stage.get("name", "unknown")
            # Report uses elapsed_ms, convert to seconds for display
            elapsed_ms = stage.get("elapsed_ms", 0)
            elapsed_s = elapsed_ms / 1000.0
            items = stage.get("items_processed", 0)
            api_calls = stage.get("api_calls", 0)
            cost = stage.get("estimated_cost_usd", 0)

            col1, col2, col3, col4 = st.columns(4)
            col1.metric(name, f"{elapsed_s:.2f}s")
            col2.metric("Items", items)
            col3.metric("API Calls", api_calls)
            col4.metric("Est. Cost", f"${cost:.3f}" if cost else "—")

    # Report uses "provider" not "provider_used"
    provider = metrics.get("provider", metrics.get("provider_used", "unknown"))
    st.markdown(f"**Provider:** `{provider}`")


def _save_uploaded_brief(uploaded) -> str:
    """Save uploaded brief to a session-specific temp directory with sanitized name."""
    safe_name = Path(uploaded.name).name  # strip directory components
    session_dir = ROOT / "temp_brief_upload" / uuid.uuid4().hex[:8]
    session_dir.mkdir(parents=True, exist_ok=True)
    dest = session_dir / safe_name
    # Verify resolved path stays inside session_dir
    if not dest.resolve().is_relative_to(session_dir.resolve()):
        raise ValueError("Invalid filename")
    dest.write_bytes(uploaded.getvalue())
    return str(dest)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🎨 AdForge")
    st.caption("Creative automation for social campaigns")
    st.divider()

    mode = st.radio(
        "Mode",
        ["Run Pipeline", "Build Brief", "View Pre-generated Samples"],
        help="Run the pipeline, interactively build a brief, or browse pre-generated outputs",
    )

    if mode == "Run Pipeline":
        st.markdown("#### Campaign Brief")
        brief_choice = st.selectbox(
            "Select a sample brief",
            list(SAMPLE_BRIEFS.keys()),
        )
        brief_path = SAMPLE_BRIEFS[brief_choice]

        uploaded = st.file_uploader(
            "Or upload a custom brief (YAML/JSON)",
            type=["yaml", "yml", "json"],
        )

        st.markdown("#### Options")
        provider = st.selectbox(
            "Image Provider",
            ["mock", "gemini", "firefly", "dalle", "auto"],
            help="Mock = no API key. Gemini = Imagen 4.0. Firefly = Adobe Firefly Services.",
        )

        # Template selection — previously CLI-only, now exposed in UI
        template_options = ["auto"] + [t.value for t in LayoutTemplate]
        template_choice = st.selectbox(
            "Layout Template",
            template_options,
            help="Auto picks the best template per product. Or force one for all creatives.",
        )
        # Show template description
        if template_choice != "auto":
            tpl = LayoutTemplate(template_choice)
            info = TEMPLATE_INFO.get(tpl, {})
            st.caption(f"{info.get('icon', '')} {info.get('desc', '')}")

        use_mock = provider == "mock"

        run_btn = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)

    elif mode == "Build Brief":
        st.markdown("#### Brief Builder")
        st.caption("Create a campaign brief interactively — no YAML needed.")
        run_btn = False

    else:
        st.markdown("#### Sample Outputs")
        sample_base = ROOT / "sample_output"
        campaigns = _find_sample_campaigns(sample_base)

        if not campaigns:
            st.warning("No pre-generated samples found in `sample_output/`.")
            st.info("Generate samples first:\n```\npython -m src.cli generate sample_briefs/beach_house_campaign.yaml -o sample_output --mock\n```")
        run_btn = False

    # Run log in sidebar
    if st.session_state.run_log:
        st.divider()
        st.markdown("#### 📋 Run Log")
        for entry in st.session_state.run_log[:5]:  # show last 5
            status = "✅" if entry["failed"] == 0 else "⚠️"
            st.caption(
                f"{status} **{entry['campaign']}** — "
                f"{entry['created']} creatives, {entry['elapsed']}, "
                f"saved {entry['time_saved']}"
            )


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

st.title("AdForge — Creative Automation Pipeline")

if mode == "Build Brief":
    # Interactive brief builder
    st.title("AdForge — Campaign Brief Builder")
    built_brief = _render_brief_builder()

    if built_brief:
        st.divider()
        st.markdown("#### Brief Preview")
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Brand:** {built_brief.brand}")
            st.markdown(f"**Campaign:** {built_brief.name}")
            st.markdown(f"**Message:** {built_brief.message}")
        with col2:
            st.markdown(f"**Region:** {built_brief.target_region}")
            st.markdown(f"**Audience:** {built_brief.target_audience}")
            st.markdown(f"**Products:** {len(built_brief.products)}")

        total = len(built_brief.products) * len(built_brief.aspect_ratios) * len(built_brief.languages)
        st.info(f"Ready to generate **{total} creatives**.")

        # Brief analysis
        analysis = analyze_brief(built_brief)
        _render_analysis({
            "score": {
                "overall": analysis.score.overall,
                "completeness": analysis.score.completeness,
                "clarity": analysis.score.clarity,
                "brand_strength": analysis.score.brand_strength,
                "targeting": analysis.score.targeting,
            },
            "strengths": analysis.strengths,
            "weaknesses": analysis.weaknesses,
        })

        # Export as YAML for use with CLI or pipeline
        import yaml as _yaml
        brief_yaml = _yaml.dump({"campaign": built_brief.model_dump(exclude_none=True)}, default_flow_style=False)
        st.download_button(
            "Download Brief (YAML)",
            data=brief_yaml,
            file_name=f"{built_brief.name.lower().replace(' ', '_')}.yaml",
            mime="text/yaml",
        )

        # Run pipeline directly from builder
        builder_provider = st.selectbox("Provider", ["mock", "gemini", "firefly", "dalle", "auto"], key="bb_provider")
        if st.button("🚀 Run Pipeline on This Brief", type="primary", key="bb_run"):
            # Save brief to temp file and run pipeline
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, dir=str(ROOT)) as f:
                f.write(brief_yaml)
                tmp_path = f.name

            with st.spinner("Running pipeline..."):
                try:
                    result = run_pipeline(
                        brief_path=tmp_path,
                        input_dir="input_assets",
                        output_dir="output",
                        mock=(builder_provider == "mock"),
                        provider_type=None if builder_provider == "auto" else builder_provider,
                    )
                    time_saved = (result.created_count * 15 - result.elapsed_seconds / 60) / 60
                    st.success(f"Generated **{result.created_count}** creatives in {result.elapsed_seconds:.1f}s")
                    _log_run(
                        campaign=campaign_name,
                        provider=builder_provider,
                        total=result.total_assets,
                        created=result.created_count,
                        failed=result.failed_count,
                        elapsed=result.elapsed_seconds,
                        time_saved_hrs=max(0, time_saved),
                    )
                    assets_data = [a.model_dump() for a in result.assets]
                    _render_gallery(assets_data)
                except Exception as e:
                    st.error(f"Pipeline failed: {e}")

elif mode == "View Pre-generated Samples":
    sample_base = ROOT / "sample_output"
    campaigns = _find_sample_campaigns(sample_base)

    if campaigns:
        selected_name = st.selectbox(
            "Select a campaign",
            [c.name.replace("_", " ").title() for c in campaigns],
        )
        selected_idx = [c.name.replace("_", " ").title() for c in campaigns].index(selected_name)
        campaign_dir = campaigns[selected_idx]

        report = _load_sample_report(campaign_dir)
        if report:
            tab_campaign, tab_gallery, tab_approval, tab_ab, tab_performance, tab_metrics = st.tabs(
                ["📋 Campaign", "🖼️ Gallery", "✅ Approval Queue", "🔀 A/B Compare", "📈 Performance", "📊 Metrics"]
            )

            with tab_campaign:
                col1, col2, col3, col4 = st.columns(4)
                col1.metric("Total Assets", report["total_assets"])
                col2.metric("Created", report["created_count"])
                col3.metric("Hero Reused", report["hero_reused_count"])
                col4.metric("Failed", report["failed_count"])

                st.markdown(f"**Campaign:** {report['campaign_name']}")
                elapsed = report.get("elapsed_seconds", 0)
                st.markdown(f"**Pipeline Time:** {elapsed:.1f}s")

                # Efficiency metrics
                efficiency = report.get("efficiency")
                if efficiency:
                    st.markdown("---")
                    st.markdown("#### ⏱ Efficiency")
                    e1, e2, e3 = st.columns(3)
                    e1.metric("Time Saved", f"{efficiency['time_saved_hours']:.1f} hours")
                    e2.metric("Speedup", f"{efficiency['speedup_factor']:.0f}×")
                    e3.metric("Manual Estimate", f"{efficiency['estimated_manual_minutes']:.0f} min")

                # ZIP download
                zip_path = campaign_dir / f"{campaign_dir.name}.zip"
                if not zip_path.exists():
                    zip_path = campaign_dir.parent / f"{campaign_dir.name}.zip"
                if zip_path.exists():
                    with open(zip_path, "rb") as zf:
                        st.download_button(
                            "📦 Download Campaign ZIP",
                            data=zf.read(),
                            file_name=zip_path.name,
                            mime="application/zip",
                            key=f"zip_sample_{selected_idx}",
                        )

                # Report uses "brief_analysis" not "analysis"
                analysis_data = report.get("brief_analysis")
                if analysis_data:
                    st.markdown("---")
                    st.markdown("#### Brief Analysis")
                    _render_analysis(analysis_data)

            with tab_gallery:
                assets = report.get("assets", [])
                patched_assets = []
                for asset in assets:
                    patched = dict(asset)
                    original = Path(patched["file_path"])
                    if not Path(patched["file_path"]).exists():
                        parts = original.parts
                        if parts and parts[0] == "sample_output":
                            patched["file_path"] = str(ROOT / original)
                        else:
                            patched["file_path"] = str(campaign_dir / Path(*parts[1:]))
                    patched_assets.append(patched)

                _render_gallery(patched_assets)

            with tab_approval:
                _render_approval_queue(patched_assets, session_key=f"sample_{selected_idx}")

            with tab_ab:
                st.markdown("#### A/B Template Comparison")
                st.caption("Preview how all 5 layout templates render with the same hero image and brief settings.")
                # Try to load the brief for this campaign to get brand guidelines
                try:
                    # Attempt to find the matching sample brief
                    brief_for_ab = None
                    for bname, bpath in SAMPLE_BRIEFS.items():
                        try:
                            b = load_brief(bpath)
                            if b.name.lower().replace(" ", "_") in campaign_dir.name:
                                brief_for_ab = b
                                break
                        except Exception:
                            continue

                    if brief_for_ab:
                        # Find a hero image from the output
                        hero_candidates = list(campaign_dir.rglob("hero*.png")) + list(campaign_dir.rglob("hero*.jpg"))
                        if not hero_candidates:
                            hero_candidates = list(campaign_dir.rglob("*.jpg"))
                        hero_for_ab = hero_candidates[0] if hero_candidates else None
                        _render_ab_comparison(brief_for_ab, hero_for_ab)
                    else:
                        st.info("Could not match a campaign brief for A/B comparison.")
                except Exception as e:
                    st.warning(f"A/B comparison unavailable: {e}")

            with tab_performance:
                _render_performance(patched_assets)

            with tab_metrics:
                _render_metrics(report)

    else:
        st.info("No pre-generated samples found. Run the pipeline with `-o sample_output` first.")

elif mode == "Run Pipeline" and run_btn:
    # Handle uploaded file
    if uploaded:
        brief_path = _save_uploaded_brief(uploaded)

    # Load and show brief
    try:
        brief = load_brief(brief_path)
    except Exception as e:
        st.error(f"Failed to load brief: {e}")
        st.stop()

    tab_campaign, tab_gallery, tab_approval, tab_ab, tab_performance, tab_metrics = st.tabs(
        ["📋 Campaign", "🖼️ Gallery", "✅ Approval Queue", "🔀 A/B Compare", "📈 Performance", "📊 Metrics"]
    )

    with tab_campaign:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"**Brand:** {brief.brand}")
            st.markdown(f"**Campaign:** {brief.name}")
            st.markdown(f"**Message:** {brief.message}")
            if brief.tagline:
                st.markdown(f"**Tagline:** {brief.tagline}")
        with col2:
            st.markdown(f"**Region:** {brief.target_region}")
            st.markdown(f"**Audience:** {brief.target_audience}")
            st.markdown(f"**Languages:** {', '.join(brief.languages)}")
            st.markdown(f"**Products:** {len(brief.products)}")
            st.markdown(f"**Ratios:** {', '.join(r.ratio for r in brief.aspect_ratios)}")

        total = len(brief.products) * len(brief.aspect_ratios) * len(brief.languages)
        st.markdown(f"**Total creatives to generate:** {total}")

        # Brief analysis
        st.markdown("---")
        st.markdown("#### Brief Analysis")
        analysis = analyze_brief(brief)
        _render_analysis({
            "score": {
                "overall": analysis.score.overall,
                "completeness": analysis.score.completeness,
                "clarity": analysis.score.clarity,
                "brand_strength": analysis.score.brand_strength,
                "targeting": analysis.score.targeting,
            },
            "strengths": analysis.strengths,
            "weaknesses": analysis.weaknesses,
        })

    # Run pipeline with template selection
    forced_template = None if template_choice == "auto" else template_choice
    with st.spinner("Running pipeline... This may take a moment."):
        try:
            result = run_pipeline(
                brief_path=brief_path,
                input_dir="input_assets",
                output_dir="output",
                mock=use_mock,
                provider_type=None if provider == "auto" else provider,
                template=forced_template,
            )
        except RuntimeError as e:
            st.error(f"Pipeline failed: {e}")
            st.stop()

    # Log this run
    time_saved_hrs = max(0, (result.created_count * 15 - result.elapsed_seconds / 60) / 60)
    _log_run(
        campaign=brief.name,
        provider=provider,
        total=result.total_assets,
        created=result.created_count,
        failed=result.failed_count,
        elapsed=result.elapsed_seconds,
        time_saved_hrs=time_saved_hrs,
    )

    with tab_campaign:
        st.markdown("---")
        st.markdown("#### Results")
        r1, r2, r3, r4 = st.columns(4)
        r1.metric("Total", result.total_assets)
        r2.metric("Created", result.created_count)
        r3.metric("Hero Reused", result.hero_reused_count)
        r4.metric("Failed", result.failed_count)
        st.markdown(f"**Time:** {result.elapsed_seconds:.1f}s")

        if result.warnings:
            with st.expander(f"⚠️ Warnings ({len(result.warnings)})"):
                for w in result.warnings:
                    st.warning(w)

    with tab_gallery:
        assets_data = [a.model_dump() for a in result.assets]
        _render_gallery(assets_data)

    with tab_approval:
        # Convert enum values to strings for the approval queue
        assets_for_approval = []
        for a in result.assets:
            d = a.model_dump()
            d["hero_status"] = d["hero_status"].value if hasattr(d["hero_status"], "value") else d["hero_status"]
            if d.get("brand_compliance") and hasattr(d["brand_compliance"].get("status", ""), "value"):
                d["brand_compliance"]["status"] = d["brand_compliance"]["status"].value
            if d.get("legal_compliance") and hasattr(d["legal_compliance"].get("status", ""), "value"):
                d["legal_compliance"]["status"] = d["legal_compliance"]["status"].value
            assets_for_approval.append(d)
        _render_approval_queue(assets_for_approval, session_key="pipeline_run")

    with tab_ab:
        st.markdown("#### A/B Template Comparison")
        st.caption("Compare all 5 layout templates side-by-side using the generated hero images.")
        # Find first generated hero for A/B preview
        from src.storage import StorageManager as _SM, slugify as _slugify
        _st = _SM(input_dir=Path("input_assets"), output_dir=Path("output"))
        for product in brief.products:
            st.markdown(f"**{product.name}**")
            hero_dir = _st.get_campaign_dir(brief.name) / _slugify(product.id)
            hero_candidates = list(hero_dir.rglob("hero*.png")) + list(hero_dir.rglob("hero*.jpg"))
            if hero_candidates:
                _render_ab_comparison(brief, hero_candidates[0])
            else:
                st.info(f"No hero found for {product.name}")
            st.divider()

    with tab_performance:
        _render_performance(assets_data)

    with tab_metrics:
        from src.storage import StorageManager
        storage = StorageManager(input_dir=Path("input_assets"), output_dir=Path("output"))
        campaign_dir = storage.get_campaign_dir(brief.name)
        report = _load_sample_report(campaign_dir)
        if report:
            _render_metrics(report)
        else:
            st.info("Metrics available in the JSON report.")

elif mode == "Run Pipeline":
    # Show brief preview before running
    brief_path_current = SAMPLE_BRIEFS[brief_choice] if not uploaded else None
    if brief_path_current:
        try:
            brief = load_brief(brief_path_current)
            col1, col2 = st.columns(2)
            with col1:
                st.markdown(f"**Brand:** {brief.brand}")
                st.markdown(f"**Campaign:** {brief.name}")
                st.markdown(f"**Message:** {brief.message}")
                if brief.tagline:
                    st.markdown(f"**Tagline:** {brief.tagline}")
            with col2:
                st.markdown(f"**Region:** {brief.target_region}")
                st.markdown(f"**Audience:** {brief.target_audience}")
                st.markdown(f"**Languages:** {', '.join(brief.languages)}")
                st.markdown(f"**Products:** {len(brief.products)}")

            total = len(brief.products) * len(brief.aspect_ratios) * len(brief.languages)
            st.info(f"Ready to generate **{total} creatives** across {len(brief.aspect_ratios)} aspect ratios. Click **Run Pipeline** in the sidebar.")

            # Show products
            st.markdown("#### Products")
            for p in brief.products:
                with st.expander(f"📦 {p.name}"):
                    st.markdown(f"**ID:** `{p.id}`")
                    st.markdown(f"**Description:** {p.description}")
                    hero = "Will be generated via GenAI" if not p.hero_image else f"Existing: `{p.hero_image}`"
                    st.markdown(f"**Hero Image:** {hero}")
                    if p.keywords:
                        st.markdown(f"**Keywords:** {', '.join(p.keywords)}")

        except Exception:
            st.info("Select a brief and click **Run Pipeline** to begin.")
    else:
        st.info("Upload a brief file and click **Run Pipeline** to begin.")
