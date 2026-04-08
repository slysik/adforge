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
# Custom CSS — Brand Design System
# ---------------------------------------------------------------------------
CUSTOM_CSS = """
<style>
/* ── Brand Tokens ─────────────────────────────────────────────────────── */
:root {
  --ocean-blue:   #1B4F72;
  --ocean-dark:   #154060;
  --ocean-light:  #2E86C1;
  --warm-ivory:   #FDF8F3;
  --sandy-beige:  #F5E6CA;
  --shell-tan:    #D4A574;
  --shell-dark:   #B8895A;
  --charcoal:     #2C3E50;
  --charcoal-mid: #4A6274;
  --charcoal-light: #7F8C8D;
  --success:      #1E8449;
  --warning:      #B7770D;
  --danger:       #922B21;
  --radius-sm:    8px;
  --radius-md:    12px;
  --radius-lg:    20px;
  --shadow-sm:    0 1px 4px rgba(27,79,114,.08);
  --shadow-md:    0 4px 16px rgba(27,79,114,.13);
  --shadow-lg:    0 8px 32px rgba(27,79,114,.18);
  --transition:   200ms ease;
}

/* ── Global resets ────────────────────────────────────────────────────── */
html, body, [class*="css"] {
  font-family: Georgia, 'Times New Roman', serif;
  color: var(--charcoal);
}

.main .block-container {
  padding-top: 1.5rem;
  padding-bottom: 3rem;
  max-width: 1400px;
}

/* ── Sidebar ──────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
  background: var(--ocean-blue) !important;
  border-right: none;
}
[data-testid="stSidebar"] * {
  color: #E8F4FD !important;
}
[data-testid="stSidebar"] .stRadio label {
  color: #E8F4FD !important;
}
[data-testid="stSidebar"] hr {
  border-color: rgba(255,255,255,.18) !important;
}
[data-testid="stSidebar"] .stSelectbox > div > div {
  background: rgba(255,255,255,.1) !important;
  border-color: rgba(255,255,255,.25) !important;
  color: #fff !important;
}
[data-testid="stSidebar"] [data-testid="stFileUploader"] {
  background: rgba(255,255,255,.08) !important;
  border-color: rgba(255,255,255,.2) !important;
  border-radius: var(--radius-md) !important;
}
[data-testid="stSidebar"] .stButton > button {
  background: var(--shell-tan) !important;
  color: var(--charcoal) !important;
  border: none !important;
  font-weight: 600 !important;
  border-radius: var(--radius-md) !important;
  transition: background var(--transition), transform var(--transition) !important;
}
[data-testid="stSidebar"] .stButton > button:hover {
  background: var(--shell-dark) !important;
  transform: translateY(-1px) !important;
}

/* ── Tabs ─────────────────────────────────────────────────────────────── */
[data-testid="stTabs"] [role="tablist"] {
  gap: 2px;
  border-bottom: 2px solid var(--sandy-beige) !important;
  background: transparent;
}
[data-testid="stTabs"] [role="tab"] {
  background: transparent;
  border: none !important;
  border-radius: var(--radius-sm) var(--radius-sm) 0 0 !important;
  padding: .6rem 1.2rem !important;
  font-size: .85rem;
  font-weight: 500;
  color: var(--charcoal-mid) !important;
  transition: background var(--transition), color var(--transition) !important;
}
[data-testid="stTabs"] [role="tab"]:hover {
  background: var(--sandy-beige) !important;
  color: var(--ocean-blue) !important;
}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
  background: var(--ocean-blue) !important;
  color: #fff !important;
  font-weight: 600 !important;
}

/* ── Primary buttons ──────────────────────────────────────────────────── */
.stButton > button[kind="primary"], .stButton > button[data-baseweb="button"] {
  background: var(--ocean-blue) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  padding: .6rem 1.5rem !important;
  transition: background var(--transition), box-shadow var(--transition), transform var(--transition) !important;
  box-shadow: var(--shadow-sm) !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--ocean-dark) !important;
  box-shadow: var(--shadow-md) !important;
  transform: translateY(-1px) !important;
}
.stButton > button[kind="secondary"] {
  background: transparent !important;
  color: var(--ocean-blue) !important;
  border: 1.5px solid var(--ocean-blue) !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  transition: background var(--transition) !important;
}
.stButton > button[kind="secondary"]:hover {
  background: rgba(27,79,114,.06) !important;
}

/* ── Metrics ──────────────────────────────────────────────────────────── */
[data-testid="stMetric"] {
  background: #fff;
  border: 1px solid var(--sandy-beige);
  border-radius: var(--radius-md);
  padding: 1rem 1.2rem;
  box-shadow: var(--shadow-sm);
}
[data-testid="stMetricLabel"] { color: var(--charcoal-mid) !important; font-size: .78rem !important; }
[data-testid="stMetricValue"] { color: var(--ocean-blue) !important; font-size: 1.6rem !important; }

/* ── Expanders ────────────────────────────────────────────────────────── */
[data-testid="stExpander"] {
  border: 1px solid var(--sandy-beige) !important;
  border-radius: var(--radius-md) !important;
  margin-bottom: .6rem !important;
  overflow: hidden !important;
}
[data-testid="stExpander"] summary {
  background: var(--warm-ivory) !important;
  padding: .75rem 1rem !important;
  font-weight: 500 !important;
}

/* ── Info / success / warning / error boxes ───────────────────────────── */
[data-testid="stAlert"] {
  border-radius: var(--radius-md) !important;
}

/* ── Dataframe ────────────────────────────────────────────────────────── */
[data-testid="stDataFrame"] {
  border-radius: var(--radius-md) !important;
  overflow: hidden !important;
  border: 1px solid var(--sandy-beige) !important;
}

/* ── Progress bar ─────────────────────────────────────────────────────── */
[data-testid="stProgress"] > div > div > div {
  background: var(--ocean-blue) !important;
}

/* ── Custom card utility ──────────────────────────────────────────────── */
.af-card {
  background: #fff;
  border: 1px solid var(--sandy-beige);
  border-radius: var(--radius-md);
  padding: 1.25rem 1.5rem;
  box-shadow: var(--shadow-sm);
  margin-bottom: 1rem;
  transition: box-shadow var(--transition);
}
.af-card:hover { box-shadow: var(--shadow-md); }

.af-card-ocean {
  background: var(--ocean-blue);
  color: #fff;
  border: none;
}
.af-card-ocean * { color: #fff !important; }

/* ── Hero banner ──────────────────────────────────────────────────────── */
.af-hero {
  background: linear-gradient(135deg, var(--ocean-blue) 0%, var(--ocean-light) 55%, #4AA3DF 100%);
  border-radius: var(--radius-lg);
  padding: 2.5rem 2.5rem 2rem;
  margin-bottom: 1.75rem;
  position: relative;
  overflow: hidden;
}
.af-hero::before {
  content: '';
  position: absolute;
  top: -40px; right: -40px;
  width: 200px; height: 200px;
  background: rgba(255,255,255,.06);
  border-radius: 50%;
}
.af-hero::after {
  content: '';
  position: absolute;
  bottom: -60px; left: 30%;
  width: 280px; height: 280px;
  background: rgba(255,255,255,.04);
  border-radius: 50%;
}
.af-hero h1 {
  color: #fff !important;
  font-size: 2.1rem !important;
  font-weight: 700 !important;
  margin: 0 0 .4rem !important;
  line-height: 1.2 !important;
}
.af-hero p {
  color: rgba(255,255,255,.82) !important;
  font-size: 1rem !important;
  margin: 0 !important;
  max-width: 560px;
}
.af-hero-badge {
  display: inline-block;
  background: rgba(255,255,255,.15);
  color: #fff;
  font-size: .75rem;
  font-weight: 600;
  letter-spacing: .05em;
  text-transform: uppercase;
  padding: .25rem .75rem;
  border-radius: 100px;
  margin-bottom: .85rem;
}
.af-hero-meta {
  display: flex;
  gap: 2rem;
  margin-top: 1.25rem;
  flex-wrap: wrap;
}
.af-hero-meta-item {
  display: flex;
  flex-direction: column;
}
.af-hero-meta-label {
  font-size: .72rem;
  color: rgba(255,255,255,.6);
  text-transform: uppercase;
  letter-spacing: .06em;
  margin-bottom: .1rem;
}
.af-hero-meta-value {
  font-size: .92rem;
  color: #fff;
  font-weight: 600;
}

/* ── Pipeline stepper ─────────────────────────────────────────────────── */
.af-stepper {
  display: flex;
  align-items: flex-start;
  gap: 0;
  margin: 1.5rem 0;
  overflow-x: auto;
  padding-bottom: .5rem;
}
.af-step {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  min-width: 80px;
  position: relative;
  text-align: center;
}
.af-step:not(:last-child)::after {
  content: '';
  position: absolute;
  top: 16px;
  left: calc(50% + 16px);
  right: calc(-50% + 16px);
  height: 2px;
  background: var(--sandy-beige);
  z-index: 0;
}
.af-step.done:not(:last-child)::after,
.af-step.active:not(:last-child)::after {
  background: var(--ocean-light);
}
.af-step-circle {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: .78rem;
  font-weight: 700;
  z-index: 1;
  position: relative;
  border: 2px solid var(--sandy-beige);
  background: #fff;
  color: var(--charcoal-light);
  transition: all var(--transition);
}
.af-step.done .af-step-circle {
  background: var(--ocean-blue);
  border-color: var(--ocean-blue);
  color: #fff;
}
.af-step.active .af-step-circle {
  background: var(--shell-tan);
  border-color: var(--shell-tan);
  color: var(--charcoal);
  box-shadow: 0 0 0 4px rgba(212,165,116,.25);
}
.af-step-label {
  font-size: .65rem;
  color: var(--charcoal-light);
  margin-top: .4rem;
  line-height: 1.3;
  max-width: 72px;
  font-weight: 500;
}
.af-step.done .af-step-label { color: var(--ocean-blue); }
.af-step.active .af-step-label { color: var(--charcoal); font-weight: 700; }

/* ── Gallery grid ─────────────────────────────────────────────────────── */
.af-gallery-product {
  margin-bottom: 2.5rem;
}
.af-gallery-product-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--ocean-blue);
  margin-bottom: .25rem;
  display: flex;
  align-items: center;
  gap: .5rem;
}
.af-gallery-lang-badge {
  display: inline-block;
  background: var(--sandy-beige);
  color: var(--charcoal);
  font-size: .7rem;
  font-weight: 700;
  padding: .15rem .55rem;
  border-radius: 100px;
  text-transform: uppercase;
  letter-spacing: .08em;
  margin-bottom: .75rem;
}
.af-gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
  margin-bottom: 1.25rem;
}
.af-gallery-card {
  background: #fff;
  border: 1px solid var(--sandy-beige);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  transition: box-shadow var(--transition), transform var(--transition);
  position: relative;
}
.af-gallery-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}
.af-gallery-card img {
  width: 100%;
  display: block;
  object-fit: cover;
}
.af-gallery-card-footer {
  padding: .5rem .75rem;
  border-top: 1px solid var(--sandy-beige);
  background: var(--warm-ivory);
}
.af-gallery-ratio {
  font-size: .72rem;
  font-weight: 700;
  color: var(--ocean-blue);
}
.af-gallery-compliance {
  font-size: .68rem;
  color: var(--charcoal-mid);
  margin-top: .15rem;
}
.af-badge {
  display: inline-block;
  font-size: .65rem;
  font-weight: 700;
  padding: .15rem .45rem;
  border-radius: 100px;
  text-transform: uppercase;
  letter-spacing: .05em;
}
.af-badge-passed  { background: #D5F5E3; color: var(--success); }
.af-badge-warning { background: #FEF9E7; color: var(--warning); }
.af-badge-failed  { background: #FDEDEC; color: var(--danger); }
.af-badge-default { background: var(--sandy-beige); color: var(--charcoal-mid); }

/* ── Metric cards ─────────────────────────────────────────────────────── */
.af-metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
  gap: 1rem;
  margin-bottom: 1.5rem;
}
.af-metric-card {
  background: #fff;
  border: 1px solid var(--sandy-beige);
  border-radius: var(--radius-md);
  padding: 1.2rem 1.3rem 1rem;
  box-shadow: var(--shadow-sm);
  position: relative;
  overflow: hidden;
  transition: box-shadow var(--transition);
}
.af-metric-card:hover { box-shadow: var(--shadow-md); }
.af-metric-card-icon {
  position: absolute;
  right: 1rem;
  top: .8rem;
  font-size: 2rem;
  opacity: .1;
}
.af-metric-label {
  font-size: .72rem;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: var(--charcoal-mid);
  margin-bottom: .3rem;
  font-weight: 600;
}
.af-metric-value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--ocean-blue);
  line-height: 1;
  margin-bottom: .25rem;
}
.af-metric-sub {
  font-size: .72rem;
  color: var(--charcoal-light);
}
.af-metric-bar {
  height: 4px;
  border-radius: 2px;
  background: var(--sandy-beige);
  margin-top: .75rem;
  overflow: hidden;
}
.af-metric-bar-fill {
  height: 100%;
  border-radius: 2px;
  background: linear-gradient(90deg, var(--ocean-blue), var(--ocean-light));
}

/* ── Approval cards ───────────────────────────────────────────────────── */
.af-approval-card {
  border: 1.5px solid var(--sandy-beige);
  border-radius: var(--radius-md);
  overflow: hidden;
  box-shadow: var(--shadow-sm);
  margin-bottom: 1rem;
  transition: box-shadow var(--transition);
}
.af-approval-card:hover { box-shadow: var(--shadow-md); }
.af-approval-card.approved { border-color: #52BE80; }
.af-approval-card.rejected { border-color: #EC7063; }
.af-approval-card.pending  { border-color: var(--shell-tan); }

.af-approval-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: .65rem 1rem;
  font-size: .82rem;
  font-weight: 600;
}
.af-approval-header.approved { background: #EAFAF1; color: var(--success); }
.af-approval-header.rejected { background: #FDEDEC; color: var(--danger); }
.af-approval-header.pending  { background: #FEF9E7; color: var(--warning); }

/* ── Brief builder wizard ─────────────────────────────────────────────── */
.af-wizard-steps {
  display: flex;
  gap: 0;
  margin-bottom: 2rem;
  border-bottom: 2px solid var(--sandy-beige);
}
.af-wizard-step {
  flex: 1;
  text-align: center;
  padding: .75rem .5rem;
  font-size: .78rem;
  font-weight: 600;
  color: var(--charcoal-light);
  cursor: pointer;
  border-bottom: 3px solid transparent;
  margin-bottom: -2px;
  transition: color var(--transition), border-color var(--transition);
}
.af-wizard-step.active {
  color: var(--ocean-blue);
  border-bottom-color: var(--ocean-blue);
}
.af-wizard-step.done {
  color: var(--success);
  border-bottom-color: var(--success);
}

/* ── Color swatch ─────────────────────────────────────────────────────── */
.af-swatches {
  display: flex;
  gap: .5rem;
  flex-wrap: wrap;
  margin: .5rem 0;
}
.af-swatch {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-sm);
  border: 2px solid rgba(0,0,0,.08);
  box-shadow: var(--shadow-sm);
}

/* ── Analysis score bar ───────────────────────────────────────────────── */
.af-score-bar-wrap {
  background: var(--sandy-beige);
  border-radius: 100px;
  height: 10px;
  overflow: hidden;
  margin: .4rem 0 .2rem;
}
.af-score-bar {
  height: 100%;
  border-radius: 100px;
  background: linear-gradient(90deg, var(--ocean-blue), var(--ocean-light));
  transition: width .6s ease;
}

/* ── Section headings ─────────────────────────────────────────────────── */
.af-section-title {
  font-size: 1.05rem;
  font-weight: 700;
  color: var(--ocean-blue);
  margin: 1.5rem 0 .75rem;
  display: flex;
  align-items: center;
  gap: .4rem;
}
.af-section-title::after {
  content: '';
  flex: 1;
  height: 1px;
  background: var(--sandy-beige);
  margin-left: .5rem;
}

/* ── Run log entry ────────────────────────────────────────────────────── */
.af-log-entry {
  background: rgba(255,255,255,.08);
  border-radius: var(--radius-sm);
  padding: .45rem .7rem;
  margin-bottom: .35rem;
  font-size: .76rem;
  color: rgba(255,255,255,.82) !important;
  border-left: 3px solid var(--shell-tan);
}

/* ── Campaign brief preview card ──────────────────────────────────────── */
.af-brief-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: .5rem 2rem;
  font-size: .88rem;
}
.af-brief-label {
  color: var(--charcoal-mid);
  font-size: .72rem;
  text-transform: uppercase;
  letter-spacing: .06em;
  font-weight: 600;
}
.af-brief-value {
  color: var(--charcoal);
  font-weight: 500;
  margin-bottom: .5rem;
}

/* ── Divider ─────────────────────────────────────────────────────────── */
hr { border-color: var(--sandy-beige) !important; margin: 1.25rem 0 !important; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

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
    "passed":      "✅",
    "warning":     "⚠️",
    "failed":      "❌",
    "not_checked": "—",
}

TEMPLATE_INFO = {
    LayoutTemplate.PRODUCT_HERO: {
        "label": "Product Hero",
        "desc":  "Full-bleed hero image with gradient overlay and text at bottom. Universally safe.",
        "icon":  "🖼️",
    },
    LayoutTemplate.EDITORIAL: {
        "label": "Editorial",
        "desc":  "60/40 hero–panel split with magazine-style text block. Best for longer messages.",
        "icon":  "📰",
    },
    LayoutTemplate.SPLIT_PANEL: {
        "label": "Split Panel",
        "desc":  "50/50 image and branded text panel. Auto-adapts orientation to format.",
        "icon":  "📐",
    },
    LayoutTemplate.MINIMAL: {
        "label": "Minimal",
        "desc":  "Centered hero at 60% scale with generous whitespace. Premium feel.",
        "icon":  "✨",
    },
    LayoutTemplate.BOLD_TYPE: {
        "label": "Bold Type",
        "desc":  "Oversized typography over tinted hero background. Punchy and direct.",
        "icon":  "🔤",
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


# ---------------------------------------------------------------------------
# UI Component helpers
# ---------------------------------------------------------------------------

def render_hero_header(title: str, subtitle: str, meta: list[tuple[str, str]] | None = None, badge: str = ""):
    meta_html = ""
    if meta:
        items = "".join(
            f'<div class="af-hero-meta-item">'
            f'<span class="af-hero-meta-label">{label}</span>'
            f'<span class="af-hero-meta-value">{value}</span>'
            f'</div>'
            for label, value in meta
        )
        meta_html = f'<div class="af-hero-meta">{items}</div>'

    badge_html = f'<div class="af-hero-badge">{badge}</div>' if badge else ""

    st.markdown(
        f"""
        <div class="af-hero">
          {badge_html}
          <h1>🎨 {title}</h1>
          <p>{subtitle}</p>
          {meta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_pipeline_stepper(active_stage: int = 0, done_stages: int = 0):
    """
    Render a horizontal 7-step pipeline progress indicator.
    active_stage: 1-indexed stage currently running (0 = not started).
    done_stages:  count of completed stages.
    """
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
            f'</div>'
        )
    st.markdown(
        f'<div class="af-stepper">{steps_html}</div>',
        unsafe_allow_html=True,
    )


def render_metric_cards(metrics: list[dict]):
    """
    Render branded metric cards.
    Each dict: {label, value, sub, icon, bar_pct (0-100, optional)}
    """
    cards_html = '<div class="af-metric-grid">'
    for m in metrics:
        bar_html = ""
        pct = m.get("bar_pct")
        if pct is not None:
            bar_html = (
                f'<div class="af-metric-bar">'
                f'<div class="af-metric-bar-fill" style="width:{min(pct,100):.0f}%"></div>'
                f'</div>'
            )
        cards_html += (
            f'<div class="af-metric-card">'
            f'<div class="af-metric-card-icon">{m.get("icon","")}</div>'
            f'<div class="af-metric-label">{m["label"]}</div>'
            f'<div class="af-metric-value">{m["value"]}</div>'
            f'<div class="af-metric-sub">{m.get("sub","")}</div>'
            f'{bar_html}'
            f'</div>'
        )
    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)


def render_section_title(text: str):
    st.markdown(f'<div class="af-section-title">{text}</div>', unsafe_allow_html=True)


def _compliance_badge(status: str) -> str:
    cls_map = {"passed": "passed", "warning": "warning", "failed": "failed"}
    cls = cls_map.get(status, "default")
    label_map = {"passed": "✓ Brand", "warning": "⚠ Brand", "failed": "✗ Brand", "not_checked": "— Brand"}
    return f'<span class="af-badge af-badge-{cls}">{label_map.get(status, status)}</span>'


def _render_ab_comparison(brief, sample_hero_path: Path | None = None):
    from PIL import Image as PILImage

    if sample_hero_path is None or not sample_hero_path.exists():
        st.info("No hero image available for A/B preview. Run the pipeline first or provide a hero asset.")
        return

    hero = PILImage.open(str(sample_hero_path)).convert("RGBA")
    bg = brief.brand_guidelines

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

        auto = auto_select_template(ratio.ratio, brief.products[0].keywords, brief.message)
        if template == auto:
            with col:
                st.success("Auto-selected")


def _render_brief_builder():
    from src.models import CampaignBrief, Product, AspectRatio, BrandGuidelines

    # Wizard step state
    if "bb_step" not in st.session_state:
        st.session_state.bb_step = 1

    step = st.session_state.bb_step

    wizard_html = '<div class="af-wizard-steps">'
    steps_def = [
        (1, "Campaign Info"),
        (2, "Brand Guidelines"),
        (3, "Products"),
        (4, "Review"),
    ]
    for s_num, s_label in steps_def:
        if s_num < step:
            cls = "done"
        elif s_num == step:
            cls = "active"
        else:
            cls = ""
        wizard_html += f'<div class="af-wizard-step {cls}">{"✓ " if s_num < step else f"{s_num}. "}{s_label}</div>'
    wizard_html += "</div>"
    st.markdown(wizard_html, unsafe_allow_html=True)

    if step == 1:
        render_section_title("Campaign Info")
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.bb_name     = st.text_input("Campaign Name",    value=st.session_state.get("bb_name", "My Campaign 2025"))
            st.session_state.bb_brand    = st.text_input("Brand Name",       value=st.session_state.get("bb_brand", "Blue Beach House Designs"))
            st.session_state.bb_msg      = st.text_area("Campaign Message",  value=st.session_state.get("bb_msg", "Handcrafted coastal elegance for your home"), height=80)
            st.session_state.bb_tagline  = st.text_input("Tagline (optional)", value=st.session_state.get("bb_tagline", ""))
        with col2:
            st.session_state.bb_region   = st.text_input("Target Region",    value=st.session_state.get("bb_region", "Southern Florida — Naples & Palm Beach"))
            st.session_state.bb_audience = st.text_input("Target Audience",  value=st.session_state.get("bb_audience", "Home decor designers, interior stylists, ages 30-60"))
            st.session_state.bb_langs    = st.multiselect("Languages", ["en", "es", "fr", "de", "pt", "ja", "zh", "ko"], default=st.session_state.get("bb_langs", ["en"]))
        if st.button("Next →", type="primary"):
            st.session_state.bb_step = 2
            st.rerun()
        return None

    elif step == 2:
        render_section_title("Brand Guidelines")
        gc1, gc2, gc3 = st.columns(3)
        with gc1:
            st.session_state.bb_c1     = st.color_picker("Primary Color",   st.session_state.get("bb_c1", "#1B4F72"))
            st.session_state.bb_c2     = st.color_picker("Secondary Color", st.session_state.get("bb_c2", "#F5E6CA"))
        with gc2:
            st.session_state.bb_c3     = st.color_picker("Tertiary Color",  st.session_state.get("bb_c3", "#FFFFFF"))
            st.session_state.bb_accent = st.color_picker("Accent Color",    st.session_state.get("bb_accent", "#D4A574"))
        with gc3:
            st.session_state.bb_font       = st.selectbox("Font Family",     ["Georgia", "Helvetica", "Arial", "Times"], index=["Georgia", "Helvetica", "Arial", "Times"].index(st.session_state.get("bb_font", "Georgia")))
            st.session_state.bb_prohibited = st.text_input("Prohibited Words (comma-separated)", value=st.session_state.get("bb_prohibited", "cheap, fake, plastic"))

        # Live swatch preview
        colors = [st.session_state.bb_c1, st.session_state.bb_c2, st.session_state.bb_c3, st.session_state.bb_accent]
        labels = ["Primary", "Secondary", "Tertiary", "Accent"]
        swatch_items = "".join(
            f'<div style="text-align:center">'
            f'<div class="af-swatch" style="background:{c};"></div>'
            f'<div style="font-size:.65rem;margin-top:.2rem;color:#7F8C8D">{l}</div>'
            f'</div>'
            for c, l in zip(colors, labels)
        )
        st.markdown(f'<div class="af-swatches">{swatch_items}</div>', unsafe_allow_html=True)

        st.session_state.bb_disclaimer = st.text_input("Legal Disclaimer (optional)", value=st.session_state.get("bb_disclaimer", ""))

        col_back, col_next = st.columns(2)
        if col_back.button("← Back"):
            st.session_state.bb_step = 1
            st.rerun()
        if col_next.button("Next →", type="primary"):
            st.session_state.bb_step = 3
            st.rerun()
        return None

    elif step == 3:
        render_section_title("Products")
        num_products = st.number_input("Number of Products", min_value=2, max_value=10, value=st.session_state.get("bb_nprods", 2), key="bb_nprods")

        products_data = []
        for i in range(int(num_products)):
            with st.expander(f"📦 Product {i + 1}", expanded=(i < 2)):
                pc1, pc2 = st.columns(2)
                with pc1:
                    p_name = st.text_input("Product Name", value=st.session_state.get(f"bb_pname_{i}", f"Product {i + 1}"), key=f"bb_pname_{i}")
                    p_id   = st.text_input("Product ID (lowercase, hyphens)", value=st.session_state.get(f"bb_pid_{i}", f"product-{i + 1}"), key=f"bb_pid_{i}")
                with pc2:
                    p_desc = st.text_area("Description", value=st.session_state.get(f"bb_pdesc_{i}", "A beautiful handcrafted product"), key=f"bb_pdesc_{i}", height=68)
                    p_kw   = st.text_input("Keywords (comma-separated)", value=st.session_state.get(f"bb_pkw_{i}", "handcrafted, coastal, design"), key=f"bb_pkw_{i}")
                products_data.append({"id": p_id.strip(), "name": p_name.strip(), "description": p_desc.strip(), "keywords": [k.strip() for k in p_kw.split(",") if k.strip()]})

        st.session_state.bb_products_data = products_data

        col_back, col_next = st.columns(2)
        if col_back.button("← Back"):
            st.session_state.bb_step = 2
            st.rerun()
        if col_next.button("Review →", type="primary"):
            st.session_state.bb_step = 4
            st.rerun()
        return None

    else:  # step 4 — Review
        render_section_title("Review & Confirm")
        brief_dict = {
            "name":     st.session_state.get("bb_name", "My Campaign"),
            "brand":    st.session_state.get("bb_brand", "Brand"),
            "message":  st.session_state.get("bb_msg", ""),
            "tagline":  st.session_state.get("bb_tagline") or None,
            "target_region":   st.session_state.get("bb_region", ""),
            "target_audience": st.session_state.get("bb_audience", ""),
            "languages": st.session_state.get("bb_langs", ["en"]),
            "brand_guidelines": {
                "primary_colors": [
                    st.session_state.get("bb_c1", "#1B4F72").upper(),
                    st.session_state.get("bb_c2", "#F5E6CA").upper(),
                    st.session_state.get("bb_c3", "#FFFFFF").upper(),
                ],
                "accent_color":    st.session_state.get("bb_accent", "#D4A574").upper(),
                "font_family":     st.session_state.get("bb_font", "Georgia"),
                "prohibited_words": [w.strip() for w in st.session_state.get("bb_prohibited", "").split(",") if w.strip()],
                "required_disclaimer": st.session_state.get("bb_disclaimer") or None,
            },
            "products": st.session_state.get("bb_products_data", []),
            "aspect_ratios": [
                {"name": "instagram_square",  "ratio": "1:1",  "width": 1080, "height": 1080},
                {"name": "stories",           "ratio": "9:16", "width": 1080, "height": 1920},
                {"name": "facebook_landscape","ratio": "16:9", "width": 1920, "height": 1080},
            ],
        }

        try:
            brief = CampaignBrief(**brief_dict)
        except Exception as e:
            st.warning(f"Brief validation: {e}")
            if st.button("← Back"):
                st.session_state.bb_step = 3
                st.rerun()
            return None

        # Brief card preview
        meta_left  = [("Brand", brief.brand), ("Campaign", brief.name), ("Message", brief.message)]
        meta_right = [("Region", brief.target_region), ("Audience", brief.target_audience), ("Products", str(len(brief.products)))]
        rows = "".join(
            f'<div><div class="af-brief-label">{l}</div><div class="af-brief-value">{v}</div></div>'
            for (l, v) in meta_left + meta_right
        )
        st.markdown(f'<div class="af-card"><div class="af-brief-grid">{rows}</div></div>', unsafe_allow_html=True)

        total = len(brief.products) * 3 * len(brief.languages)
        st.info(f"Ready to generate **{total} creatives** (3 aspect ratios × {len(brief.products)} products × {len(brief.languages)} language(s)).")

        col_back, _ = st.columns(2)
        if col_back.button("← Back"):
            st.session_state.bb_step = 3
            st.rerun()

        return brief


def _load_sample_report(campaign_dir: Path) -> dict | None:
    report_path = campaign_dir / "report.json"
    if report_path.exists():
        return json.loads(report_path.read_text())
    return None


def _find_sample_campaigns(base: Path) -> list[Path]:
    if not base.exists():
        return []
    return sorted([d for d in base.iterdir() if d.is_dir() and (d / "report.json").exists()])


def _render_gallery(assets: list[dict], base_dir: Path | None = None):
    products: dict[str, list] = {}
    for asset in assets:
        pid = asset["product_id"]
        if pid not in products:
            products[pid] = []
        products[pid].append(asset)

    for product_id, product_assets in products.items():
        st.markdown(f'<div class="af-gallery-product-title">📦 {product_id}</div>', unsafe_allow_html=True)

        languages = sorted(set(a["language"] for a in product_assets))

        for lang in languages:
            lang_assets = [a for a in product_assets if a["language"] == lang]
            lang_assets.sort(key=lambda a: a["aspect_ratio"])

            st.markdown(f'<span class="af-gallery-lang-badge">🌐 {lang.upper()}</span>', unsafe_allow_html=True)

            cols = st.columns(len(lang_assets))
            for col, asset in zip(cols, lang_assets):
                file_path = asset["file_path"]
                if base_dir and not Path(file_path).is_absolute():
                    file_path = str(base_dir / Path(file_path).relative_to(
                        Path(file_path).parts[0]
                    )) if Path(file_path).parts else file_path

                brand_status = asset.get("brand_compliance", {}).get("status", "not_checked")
                legal_status = asset.get("legal_compliance", {}).get("status", "not_checked")
                hero_status  = asset.get("hero_status", "generated")
                hero_icon    = "♻️" if hero_status == "reused" else "✦"

                with col:
                    if Path(file_path).exists():
                        st.image(str(file_path), use_container_width=True)
                    else:
                        st.warning(f"File not found: {file_path}")
                    st.markdown(
                        f'<div class="af-gallery-ratio">{asset["aspect_ratio"]}</div>'
                        f'<div class="af-gallery-compliance">'
                        f'{COMPLIANCE_EMOJI.get(brand_status,"—")} Brand &nbsp;'
                        f'{COMPLIANCE_EMOJI.get(legal_status,"—")} Legal &nbsp;'
                        f'{hero_icon} Hero'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

        st.markdown("<hr>", unsafe_allow_html=True)


def _render_analysis(analysis_data: dict):
    score   = analysis_data.get("score", {})
    overall = score.get("overall", 0)
    grade   = "A+" if overall >= 95 else "A" if overall >= 85 else "B" if overall >= 75 else "C" if overall >= 65 else "D"

    render_metric_cards([
        {"label": "Overall Score", "value": f"{overall}/100", "sub": f"Grade {grade}", "icon": "🎯", "bar_pct": overall},
        {"label": "Completeness", "value": f"{score.get('completeness', 0)}/25", "sub": "Brief coverage",  "icon": "📋", "bar_pct": score.get("completeness", 0) * 4},
        {"label": "Clarity",      "value": f"{score.get('clarity', 0)}/25",      "sub": "Message clarity","icon": "💡", "bar_pct": score.get("clarity", 0) * 4},
        {"label": "Brand Strength","value": f"{score.get('brand_strength', 0)}/25","sub": "Brand consistency","icon": "🏷️","bar_pct": score.get("brand_strength", 0) * 4},
        {"label": "Targeting",    "value": f"{score.get('targeting', 0)}/25",    "sub": "Audience fit",   "icon": "🎯", "bar_pct": score.get("targeting", 0) * 4},
    ])

    if analysis_data.get("strengths") or analysis_data.get("weaknesses"):
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


def _render_approval_queue(assets: list[dict], session_key: str = "default"):
    if not assets:
        st.info("No assets to review.")
        return

    state_key = f"approvals_{session_key}"
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            i: {"status": "pending", "comment": ""}
            for i in range(len(assets))
        }
    approvals = st.session_state[state_key]

    statuses = [approvals[i]["status"] for i in range(len(assets))]
    approved = statuses.count("approved")
    rejected = statuses.count("rejected")
    pending  = statuses.count("pending")
    total    = len(assets)
    pct_done = ((approved + rejected) / total * 100) if total else 0

    # Summary metric cards
    render_metric_cards([
        {"label": "Pending",  "value": str(pending),  "sub": "awaiting review", "icon": "⏳", "bar_pct": pending / total * 100 if total else 0},
        {"label": "Approved", "value": str(approved), "sub": "ready to publish","icon": "✅", "bar_pct": approved / total * 100 if total else 0},
        {"label": "Rejected", "value": str(rejected), "sub": "needs revision",  "icon": "❌", "bar_pct": rejected / total * 100 if total else 0},
        {"label": "Progress", "value": f"{pct_done:.0f}%", "sub": f"{approved+rejected} of {total} reviewed", "icon": "📊", "bar_pct": pct_done},
    ])

    # Bulk actions
    col_a, col_r, col_reset = st.columns(3)
    if col_a.button("✅ Approve All", key=f"approve_all_{session_key}"):
        for i in range(len(assets)):
            approvals[i]["status"] = "approved"
        st.rerun()
    if col_r.button("❌ Reject All", key=f"reject_all_{session_key}"):
        for i in range(len(assets)):
            approvals[i]["status"] = "rejected"
        st.rerun()
    if col_reset.button("🔄 Reset All", key=f"reset_all_{session_key}"):
        for i in range(len(assets)):
            approvals[i]["status"] = "pending"
            approvals[i]["comment"] = ""
        st.rerun()

    st.markdown("<hr>", unsafe_allow_html=True)

    # Per-asset cards
    for i, asset in enumerate(assets):
        pid    = asset.get("product_id", "unknown")
        ratio  = asset.get("aspect_ratio", "?")
        lang   = asset.get("language", "?")
        status = approvals[i]["status"]

        header_label = {"pending": "⏳ Pending", "approved": "✅ Approved", "rejected": "❌ Rejected"}[status]
        header_cls   = status

        with st.expander(f"{header_label} — {pid} / {ratio} / {lang}", expanded=(status == "pending")):
            img_col, ctrl_col = st.columns([2, 1])
            with img_col:
                fp = asset.get("file_path", "")
                if fp and Path(fp).exists():
                    st.image(fp, use_container_width=True)
                else:
                    st.warning("Image not available")

            with ctrl_col:
                brand  = asset.get("brand_compliance", {}).get("status", "not_checked")
                legal  = asset.get("legal_compliance", {}).get("status", "not_checked")
                hero   = asset.get("hero_status", "generated")
                st.markdown(
                    f'<div class="af-card" style="padding:.75rem 1rem">'
                    f'<div class="af-brief-label">Brand Compliance</div>'
                    f'<div class="af-brief-value">{COMPLIANCE_EMOJI.get(brand,"—")} {brand}</div>'
                    f'<div class="af-brief-label" style="margin-top:.5rem">Legal Compliance</div>'
                    f'<div class="af-brief-value">{COMPLIANCE_EMOJI.get(legal,"—")} {legal}</div>'
                    f'<div class="af-brief-label" style="margin-top:.5rem">Hero Source</div>'
                    f'<div class="af-brief-value">{"♻️ reused" if hero == "reused" else "✦ generated"}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
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

    st.markdown("<hr>", unsafe_allow_html=True)
    if st.button("Export Approval Manifest (JSON)", key=f"export_{session_key}"):
        manifest = []
        for i, asset in enumerate(assets):
            manifest.append({
                "product_id":      asset.get("product_id"),
                "aspect_ratio":    asset.get("aspect_ratio"),
                "language":        asset.get("language"),
                "file_path":       asset.get("file_path"),
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
    if not assets:
        st.info("No assets to analyze.")
        return

    perf = build_performance_report(assets)

    render_section_title("Campaign Performance (Sample Data)")
    render_metric_cards([
        {"label": "Total Spend",  "value": f"${perf.total_spend:,.0f}",  "sub": "USD",        "icon": "💰"},
        {"label": "Impressions",  "value": f"{perf.total_impressions/1000:.1f}K", "sub": "total views", "icon": "👁️"},
        {"label": "Avg CTR",      "value": f"{perf.avg_ctr:.2f}%",      "sub": "click-through rate", "icon": "🖱️"},
        {"label": "Avg CPA",      "value": f"${perf.avg_cpa:.2f}",      "sub": "cost per acquisition", "icon": "🎯"},
    ])

    if perf.winner:
        st.success(
            f"**Winner:** `{perf.winner.creative_id}` — "
            f"CTR {perf.winner.ctr:.2f}% · CPA ${perf.winner.cpa:.2f} · "
            f"{perf.winner.conversions} conversions"
        )

    render_section_title("Per-Creative KPIs")
    table_data = []
    for k in sorted(perf.kpis, key=lambda x: x.cpa):
        is_winner = perf.winner and k.creative_id == perf.winner.creative_id
        table_data.append({
            "Creative":    ("🏆 " if is_winner else "") + k.creative_id,
            "Product":     k.product_id,
            "Ratio":       k.aspect_ratio,
            "Lang":        k.language,
            "Spend":       f"${k.spend_usd:.2f}",
            "Impressions": f"{k.impressions:,}",
            "Clicks":      f"{k.clicks:,}",
            "CTR %":       f"{k.ctr:.2f}",
            "Conversions": k.conversions,
            "CPA":         f"${k.cpa:.2f}",
        })
    st.dataframe(table_data, use_container_width=True, hide_index=True)

    csv_data   = [f"{k.creative_id},{k.product_id},{k.aspect_ratio},{k.language},{k.spend_usd:.2f},{k.impressions},{k.clicks},{k.conversions},{k.ctr:.2f},{k.cpa:.2f},{k.cpc:.2f}" for k in perf.kpis]
    csv_header = "creative_id,product_id,aspect_ratio,language,spend_usd,impressions,clicks,conversions,ctr_pct,cpa_usd,cpc_usd"
    st.download_button("Download KPIs (CSV)", data=csv_header + "\n" + "\n".join(csv_data), file_name="creative_kpis.csv", mime="text/csv")
    st.caption("*Sample data generated for demo purposes. In production, this would ingest real ad platform metrics.*")


def _render_metrics(report: dict):
    metrics = report.get("metrics")
    if not metrics:
        st.info("No metrics available for this run.")
        return

    stages = metrics.get("stages", [])
    if stages:
        render_section_title("Stage Breakdown")
        cards = []
        for stage in stages:
            name       = stage.get("name", "unknown")
            elapsed_s  = stage.get("elapsed_ms", 0) / 1000.0
            items      = stage.get("items_processed", 0)
            api_calls  = stage.get("api_calls", 0)
            cost       = stage.get("estimated_cost_usd", 0)
            cards.append({
                "label": name,
                "value": f"{elapsed_s:.2f}s",
                "sub":   f"{items} items · {api_calls} API calls · {'${:.3f}'.format(cost) if cost else 'no cost'}",
                "icon":  "⚙️",
            })
        render_metric_cards(cards)

    provider = metrics.get("provider", metrics.get("provider_used", "unknown"))
    st.markdown(f"**Provider:** `{provider}`")


def _save_uploaded_brief(uploaded) -> str:
    safe_name   = Path(uploaded.name).name
    session_dir = ROOT / "temp_brief_upload" / uuid.uuid4().hex[:8]
    session_dir.mkdir(parents=True, exist_ok=True)
    dest = session_dir / safe_name
    if not dest.resolve().is_relative_to(session_dir.resolve()):
        raise ValueError("Invalid filename")
    dest.write_bytes(uploaded.getvalue())
    return str(dest)


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown(
        '<div style="font-size:1.6rem;font-weight:700;color:#fff;margin-bottom:.1rem">🎨 AdForge</div>'
        '<div style="font-size:.78rem;color:rgba(255,255,255,.6);margin-bottom:1rem">Creative automation for social campaigns</div>',
        unsafe_allow_html=True,
    )
    st.divider()

    mode = st.radio(
        "Mode",
        ["Run Pipeline", "Build Brief", "View Pre-generated Samples"],
        help="Run the pipeline, interactively build a brief, or browse pre-generated outputs",
    )

    if mode == "Run Pipeline":
        st.markdown('<div style="font-size:.82rem;font-weight:700;color:rgba(255,255,255,.7);text-transform:uppercase;letter-spacing:.08em;margin:1rem 0 .4rem">Campaign Brief</div>', unsafe_allow_html=True)
        brief_choice = st.selectbox("Select a sample brief", list(SAMPLE_BRIEFS.keys()))
        brief_path   = SAMPLE_BRIEFS[brief_choice]

        uploaded = st.file_uploader("Or upload a custom brief (YAML/JSON)", type=["yaml", "yml", "json"])

        st.markdown('<div style="font-size:.82rem;font-weight:700;color:rgba(255,255,255,.7);text-transform:uppercase;letter-spacing:.08em;margin:1rem 0 .4rem">Options</div>', unsafe_allow_html=True)
        provider = st.selectbox(
            "Image Provider",
            ["mock", "gemini", "firefly", "dalle", "auto"],
            help="Mock = no API key. Gemini = Imagen 4.0. Firefly = Adobe Firefly Services.",
        )

        template_options = ["auto"] + [t.value for t in LayoutTemplate]
        template_choice  = st.selectbox("Layout Template", template_options, help="Auto picks the best template per product.")
        if template_choice != "auto":
            tpl  = LayoutTemplate(template_choice)
            info = TEMPLATE_INFO.get(tpl, {})
            st.caption(f"{info.get('icon', '')} {info.get('desc', '')}")

        use_mock = provider == "mock"
        run_btn  = st.button("🚀 Run Pipeline", type="primary", use_container_width=True)

    elif mode == "Build Brief":
        st.markdown('<div style="font-size:.82rem;color:rgba(255,255,255,.65);margin-top:.5rem">Build a brief step-by-step — no YAML needed.</div>', unsafe_allow_html=True)
        run_btn = False

    else:
        st.markdown('<div style="font-size:.82rem;font-weight:700;color:rgba(255,255,255,.7);text-transform:uppercase;letter-spacing:.08em;margin:1rem 0 .4rem">Sample Outputs</div>', unsafe_allow_html=True)
        sample_base = ROOT / "sample_output"
        campaigns   = _find_sample_campaigns(sample_base)
        if not campaigns:
            st.warning("No pre-generated samples found in `sample_output/`.")
            st.info("Generate samples first:\n```\npython -m src.cli generate sample_briefs/beach_house_campaign.yaml -o sample_output --mock\n```")
        run_btn = False

    # Run log
    if st.session_state.run_log:
        st.divider()
        st.markdown('<div style="font-size:.78rem;font-weight:700;color:rgba(255,255,255,.7);text-transform:uppercase;letter-spacing:.08em;margin-bottom:.5rem">📋 Run Log</div>', unsafe_allow_html=True)
        for entry in st.session_state.run_log[:5]:
            status_icon = "✅" if entry["failed"] == 0 else "⚠️"
            st.markdown(
                f'<div class="af-log-entry">'
                f'{status_icon} <strong>{entry["campaign"]}</strong><br>'
                f'{entry["created"]} creatives · {entry["elapsed"]} · saved {entry["time_saved"]}'
                f'</div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

if mode == "Build Brief":
    render_hero_header(
        "Campaign Brief Builder",
        "Create a custom campaign brief step-by-step — no YAML or JSON needed.",
        badge="Brief Builder",
    )
    built_brief = _render_brief_builder()

    if built_brief:
        st.markdown("<hr>", unsafe_allow_html=True)
        render_section_title("Brief Quality Analysis")
        analysis = analyze_brief(built_brief)
        _render_analysis({
            "score": {
                "overall":       analysis.score.overall,
                "completeness":  analysis.score.completeness,
                "clarity":       analysis.score.clarity,
                "brand_strength": analysis.score.brand_strength,
                "targeting":     analysis.score.targeting,
            },
            "strengths":  analysis.strengths,
            "weaknesses": analysis.weaknesses,
        })

        import yaml as _yaml
        brief_yaml = _yaml.dump({"campaign": built_brief.model_dump(exclude_none=True)}, default_flow_style=False)
        st.download_button("Download Brief (YAML)", data=brief_yaml, file_name=f"{built_brief.name.lower().replace(' ', '_')}.yaml", mime="text/yaml")

        builder_provider = st.selectbox("Provider", ["mock", "gemini", "firefly", "dalle", "auto"], key="bb_provider")
        if st.button("🚀 Run Pipeline on This Brief", type="primary", key="bb_run"):
            import tempfile
            with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False, dir=str(ROOT)) as f:
                f.write(brief_yaml)
                tmp_path = f.name

            render_pipeline_stepper(active_stage=1)
            with st.spinner("Running pipeline..."):
                try:
                    result = run_pipeline(
                        brief_path=tmp_path,
                        input_dir="input_assets",
                        output_dir="output",
                        mock=(builder_provider == "mock"),
                        provider_type=None if builder_provider == "auto" else builder_provider,
                    )
                    render_pipeline_stepper(done_stages=7)
                    time_saved = (result.created_count * 15 - result.elapsed_seconds / 60) / 60
                    st.success(f"Generated **{result.created_count}** creatives in {result.elapsed_seconds:.1f}s")
                    _log_run(
                        campaign=built_brief.name,
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
    render_hero_header(
        "Pre-generated Samples",
        "Browse previously generated campaign creatives — no pipeline run needed.",
        badge="Sample Library",
    )
    sample_base = ROOT / "sample_output"
    campaigns   = _find_sample_campaigns(sample_base)

    if campaigns:
        selected_name = st.selectbox("Select a campaign", [c.name.replace("_", " ").title() for c in campaigns])
        selected_idx  = [c.name.replace("_", " ").title() for c in campaigns].index(selected_name)
        campaign_dir  = campaigns[selected_idx]

        report = _load_sample_report(campaign_dir)
        if report:
            tab_campaign, tab_gallery, tab_approval, tab_ab, tab_performance, tab_metrics = st.tabs(
                ["📋 Campaign", "🖼️ Gallery", "✅ Approval Queue", "🔀 A/B Compare", "📈 Performance", "📊 Metrics"]
            )

            with tab_campaign:
                elapsed    = report.get("elapsed_seconds", 0)
                efficiency = report.get("efficiency", {})
                render_metric_cards([
                    {"label": "Total Assets", "value": str(report["total_assets"]),       "sub": "generated",             "icon": "📁", "bar_pct": 100},
                    {"label": "Created",      "value": str(report["created_count"]),       "sub": "successfully composed", "icon": "✅", "bar_pct": report["created_count"] / max(report["total_assets"],1) * 100},
                    {"label": "Hero Reused",  "value": str(report["hero_reused_count"]),   "sub": "from cache",            "icon": "♻️"},
                    {"label": "Failed",       "value": str(report["failed_count"]),         "sub": "need attention",        "icon": "⚠️"},
                    {"label": "Pipeline Time","value": f"{elapsed:.1f}s",                  "sub": "end-to-end",            "icon": "⏱️"},
                    {"label": "Time Saved",   "value": f"{efficiency.get('time_saved_hours', 0):.1f}h", "sub": f"{efficiency.get('speedup_factor', 0):.0f}× speedup", "icon": "🚀"},
                ])

                zip_path = campaign_dir / f"{campaign_dir.name}.zip"
                if not zip_path.exists():
                    zip_path = campaign_dir.parent / f"{campaign_dir.name}.zip"
                if zip_path.exists():
                    with open(zip_path, "rb") as zf:
                        st.download_button("📦 Download Campaign ZIP", data=zf.read(), file_name=zip_path.name, mime="application/zip", key=f"zip_sample_{selected_idx}")

                analysis_data = report.get("brief_analysis")
                if analysis_data:
                    render_section_title("Brief Analysis")
                    _render_analysis(analysis_data)

            with tab_gallery:
                assets = report.get("assets", [])
                patched_assets = []
                for asset in assets:
                    patched  = dict(asset)
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
                render_section_title("A/B Template Comparison")
                st.caption("Preview how all 5 layout templates render with the same hero image and brief settings.")
                try:
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
    if uploaded:
        brief_path = _save_uploaded_brief(uploaded)

    try:
        brief = load_brief(brief_path)
    except Exception as e:
        st.error(f"Failed to load brief: {e}")
        st.stop()

    render_hero_header(
        brief.brand,
        brief.message,
        meta=[
            ("Campaign",   brief.name),
            ("Region",     brief.target_region),
            ("Languages",  ", ".join(brief.languages)),
            ("Products",   str(len(brief.products))),
        ],
        badge="Pipeline Running",
    )

    render_pipeline_stepper(active_stage=1)

    tab_campaign, tab_gallery, tab_approval, tab_ab, tab_performance, tab_metrics = st.tabs(
        ["📋 Campaign", "🖼️ Gallery", "✅ Approval Queue", "🔀 A/B Compare", "📈 Performance", "📊 Metrics"]
    )

    with tab_campaign:
        render_section_title("Brief Analysis")
        analysis = analyze_brief(brief)
        _render_analysis({
            "score": {
                "overall":        analysis.score.overall,
                "completeness":   analysis.score.completeness,
                "clarity":        analysis.score.clarity,
                "brand_strength": analysis.score.brand_strength,
                "targeting":      analysis.score.targeting,
            },
            "strengths":  analysis.strengths,
            "weaknesses": analysis.weaknesses,
        })

        render_section_title("Products")
        for p in brief.products:
            with st.expander(f"📦 {p.name}"):
                c1, c2 = st.columns(2)
                with c1:
                    st.markdown(f"**ID:** `{p.id}`")
                    st.markdown(f"**Description:** {p.description}")
                with c2:
                    hero_txt = "Will be generated via GenAI" if not p.hero_image else f"Existing: `{p.hero_image}`"
                    st.markdown(f"**Hero Image:** {hero_txt}")
                    if p.keywords:
                        st.markdown(f"**Keywords:** {', '.join(p.keywords)}")

    forced_template = None if template_choice == "auto" else template_choice
    with st.status("Running pipeline...", expanded=True) as status:
        try:
            result = run_pipeline(
                brief_path=brief_path,
                input_dir="input_assets",
                output_dir="output",
                mock=use_mock,
                provider_type=None if provider == "auto" else provider,
                template=forced_template,
                status_callback=lambda msg: status.update(label=msg),
            )
            status.update(label="Pipeline Complete!", state="complete", expanded=False)
        except RuntimeError as e:
            status.update(label="Pipeline Failed", state="error", expanded=False)
            st.error(f"Pipeline failed: {e}")
            st.stop()

    time_saved_hrs = max(0, (result.created_count * 15 - result.elapsed_seconds / 60) / 60)
    _log_run(campaign=brief.name, provider=provider, total=result.total_assets, created=result.created_count, failed=result.failed_count, elapsed=result.elapsed_seconds, time_saved_hrs=time_saved_hrs)

    with tab_campaign:
        st.markdown("<hr>", unsafe_allow_html=True)
        render_section_title("Results")
        render_metric_cards([
            {"label": "Total",      "value": str(result.total_assets),    "sub": "planned",          "icon": "📁", "bar_pct": 100},
            {"label": "Created",    "value": str(result.created_count),   "sub": "successfully done","icon": "✅", "bar_pct": result.created_count / max(result.total_assets,1) * 100},
            {"label": "Hero Reused","value": str(result.hero_reused_count),"sub": "from cache",       "icon": "♻️"},
            {"label": "Failed",     "value": str(result.failed_count),    "sub": "errors",           "icon": "⚠️"},
            {"label": "Time",       "value": f"{result.elapsed_seconds:.1f}s","sub": "pipeline duration","icon": "⏱️"},
            {"label": "Saved",      "value": f"{time_saved_hrs:.1f}h",    "sub": "vs manual",        "icon": "🚀"},
        ])
        if result.warnings:
            with st.expander(f"⚠️ Warnings ({len(result.warnings)})"):
                for w in result.warnings:
                    st.warning(w)

    with tab_gallery:
        assets_data = [a.model_dump() for a in result.assets]
        _render_gallery(assets_data)

    with tab_approval:
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
        render_section_title("A/B Template Comparison")
        st.caption("Compare all 5 layout templates side-by-side using the generated hero images.")
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
        storage      = StorageManager(input_dir=Path("input_assets"), output_dir=Path("output"))
        campaign_dir = storage.get_campaign_dir(brief.name)
        report       = _load_sample_report(campaign_dir)
        if report:
            _render_metrics(report)
        else:
            st.info("Metrics available in the JSON report.")

elif mode == "Run Pipeline":
    # Landing state — show brief preview
    brief_path_current = SAMPLE_BRIEFS[brief_choice] if not uploaded else None
    if brief_path_current:
        try:
            brief = load_brief(brief_path_current)
            total = len(brief.products) * len(brief.aspect_ratios) * len(brief.languages)
            render_hero_header(
                brief.brand,
                brief.message,
                meta=[
                    ("Campaign",  brief.name),
                    ("Region",    brief.target_region),
                    ("Audience",  brief.target_audience[:50] + "…" if len(brief.target_audience) > 50 else brief.target_audience),
                    ("Languages", ", ".join(brief.languages)),
                    ("Products",  str(len(brief.products))),
                ],
                badge="Ready to Run",
            )

            st.info(f"Ready to generate **{total} creatives** across {len(brief.aspect_ratios)} aspect ratios. Click **Run Pipeline** in the sidebar.")

            render_section_title("Pipeline Overview")
            render_pipeline_stepper(active_stage=0)

            render_section_title("Products")
            for p in brief.products:
                with st.expander(f"📦 {p.name}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown(f"**ID:** `{p.id}`")
                        st.markdown(f"**Description:** {p.description}")
                    with c2:
                        hero = "Will be generated via GenAI" if not p.hero_image else f"Existing: `{p.hero_image}`"
                        st.markdown(f"**Hero Image:** {hero}")
                        if p.keywords:
                            st.markdown(f"**Keywords:** {', '.join(p.keywords)}")

        except Exception:
            st.info("Select a brief and click **Run Pipeline** to begin.")
    else:
        st.info("Upload a brief file and click **Run Pipeline** to begin.")
