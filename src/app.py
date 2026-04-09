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
import streamlit.components.v1 as components

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
    initial_sidebar_state="expanded",
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
  --warm-ivory:   #F7F2EC;
  --sandy-beige:  #E8DDD0;
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
  font-family: 'DM Sans', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif;
  color: var(--charcoal);
  font-size: 1rem;
}
/* Import DM Sans from Google Fonts */
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,400;0,9..40,500;0,9..40,600;0,9..40,700;1,9..40,400&display=swap');
/* Readable base text across all Streamlit elements */
.main .block-container, .main .block-container p,
.main .block-container li, .main .block-container span,
.main .block-container label, .main .block-container div {
  font-size: 1rem;
  line-height: 1.6;
}
/* Ensure form labels are clearly readable */
.main .block-container label[data-testid="stWidgetLabel"],
.main .block-container .stRadio label,
.main .block-container .stSelectbox label,
.main .block-container .stTextInput label,
.main .block-container .stTextArea label,
.main .block-container .stNumberInput label {
  font-size: 0.92rem !important;
  font-weight: 600 !important;
  color: var(--charcoal) !important;
}
/* Radio option text */
.main .stRadio [role="radiogroup"] label {
  font-size: 0.92rem !important;
  font-weight: 500 !important;
}
/* Captions should be legible */
.main .block-container [data-testid="stCaptionContainer"] {
  font-size: 0.88rem !important;
  color: var(--charcoal-mid) !important;
  line-height: 1.5 !important;
}

/* Hide Streamlit header toolbar (Deploy button) and kill top gap */
[data-testid="stHeader"] {
  display: none !important;
}
.main .block-container {
  padding-top: 0 !important;
  padding-bottom: 2rem;
  max-width: 1500px;
  padding-left: 1.5rem !important;
  padding-right: 1.5rem !important;
}
/* Kill the top margin Streamlit adds above the first element */
.main .block-container > div:first-child {
  margin-top: 0 !important;
  padding-top: 0 !important;
}
[data-testid="stAppViewContainer"] {
  padding-top: 0 !important;
}
[data-testid="stAppViewBlockContainer"] {
  padding-top: 0 !important;
}
/* Reduce Streamlit's default vertical gaps between elements */
.main .block-container [data-testid="stVerticalBlock"] > div {
  padding-top: 0;
  padding-bottom: 0;
}

/* ── Sidebar — Narrow icon bar (always visible) ──────────────────────── */
[data-testid="collapsedControl"] {
  display: none !important;
}
[data-testid="stSidebar"] {
  background: var(--ocean-blue) !important;
  border-right: none;
  min-width: 88px !important;
  max-width: 88px !important;
  width: 88px !important;
  transform: none !important;
  transition: none !important;
}
[data-testid="stSidebar"] > div:first-child {
  width: 88px !important;
  padding: 0.5rem 0 !important;
}
/* Prevent sidebar collapse — always pinned open */
[data-testid="stSidebar"][aria-expanded="false"] {
  display: block !important;
  transform: none !important;
  margin-left: 0 !important;
  min-width: 88px !important;
  max-width: 88px !important;
  width: 88px !important;
}
[data-testid="stSidebar"] * {
  color: #E8F4FD !important;
}
/* Nav item styling */
.af-nav-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.7rem 0.3rem;
  margin: 0.2rem 0.4rem;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition);
  text-decoration: none !important;
}
.af-nav-item:hover {
  background: rgba(255,255,255,.12);
}
.af-nav-item.active {
  background: rgba(255,255,255,.18);
}
.af-nav-icon {
  font-size: 1.5rem;
  line-height: 1;
  margin-bottom: 0.2rem;
}
.af-nav-label {
  font-size: 0.65rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.04em;
  text-align: center;
  line-height: 1.2;
  color: rgba(255,255,255,.85) !important;
}
.af-nav-item.active .af-nav-label {
  color: #fff !important;
}
.af-nav-divider {
  height: 1px;
  background: rgba(255,255,255,.15);
  margin: 0.4rem 0.6rem;
}
/* Sidebar button overrides — functional but visually minimal */
[data-testid="stSidebar"] .stButton > button {
  background: transparent !important;
  color: rgba(255,255,255,.85) !important;
  border: none !important;
  font-weight: 600 !important;
  padding: 0.4rem 0.2rem !important;
  width: 100% !important;
  font-size: 0.68rem !important;
  border-radius: var(--radius-sm) !important;
  transition: background var(--transition) !important;
  margin-top: -2.8rem !important;
  position: relative;
  z-index: 10;
  height: 3.2rem !important;
  opacity: 0;
}
[data-testid="stSidebar"] .stButton > button:hover {
  opacity: 1;
  background: rgba(255,255,255,.08) !important;
}
/* Hide sidebar close button */
[data-testid="stSidebar"] [data-testid="stSidebarCloseButton"] {
  display: none !important;
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
  padding: .65rem 1.3rem !important;
  font-size: 0.95rem;
  font-weight: 600;
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

/* ── Primary buttons (Run Pipeline, main CTAs) ───────────────────────── */
.stButton > button[kind="primary"] {
  background: var(--ocean-blue) !important;
  color: #fff !important;
  border: none !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  font-size: 0.95rem !important;
  padding: .65rem 1.5rem !important;
  transition: background var(--transition), box-shadow var(--transition), transform var(--transition) !important;
  box-shadow: var(--shadow-sm) !important;
}
.stButton > button[kind="primary"]:hover {
  background: var(--ocean-dark) !important;
  box-shadow: var(--shadow-md) !important;
  transform: translateY(-1px) !important;
}
/* ── Default buttons (bulk actions, export, secondary) ────────────────── */
.stButton > button[data-baseweb="button"]:not([kind="primary"]) {
  background: var(--warm-ivory) !important;
  color: var(--charcoal) !important;
  border: 1.5px solid var(--sandy-beige) !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  font-size: 0.9rem !important;
  padding: .55rem 1.2rem !important;
  transition: background var(--transition), border-color var(--transition) !important;
  box-shadow: none !important;
}
.stButton > button[data-baseweb="button"]:not([kind="primary"]):hover {
  background: var(--sandy-beige) !important;
  border-color: var(--shell-tan) !important;
}
/* ── Download buttons ─────────────────────────────────────────────────── */
.stDownloadButton > button {
  background: var(--warm-ivory) !important;
  color: var(--charcoal) !important;
  border: 1.5px solid var(--sandy-beige) !important;
  border-radius: var(--radius-md) !important;
  font-weight: 600 !important;
  font-size: 0.9rem !important;
}
.stDownloadButton > button:hover {
  background: var(--sandy-beige) !important;
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
[data-testid="stMetricLabel"] { color: var(--charcoal-mid) !important; font-size: .88rem !important; }
[data-testid="stMetricValue"] { color: var(--ocean-blue) !important; font-size: 1.7rem !important; }

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
  font-size: .95rem !important;
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

/* ── Hero banner (compact) ────────────────────────────────────────────── */
.af-hero {
  background: linear-gradient(135deg, var(--ocean-blue) 0%, var(--ocean-light) 55%, #4AA3DF 100%);
  border-radius: var(--radius-lg);
  padding: .9rem 1.5rem;
  margin-top: 0 !important;
  margin-bottom: .5rem;
  display: flex;
  align-items: center;
  gap: 1rem;
  position: relative;
  overflow: hidden;
}
.af-hero::before, .af-hero::after { display: none; }
.af-hero h1 {
  color: #fff !important;
  font-size: 1.3rem !important;
  font-weight: 700 !important;
  margin: 0 !important;
  line-height: 1.2 !important;
  white-space: nowrap;
}
.af-hero p {
  color: rgba(255,255,255,.9) !important;
  font-size: 1.05rem !important;
  margin: 0 !important;
}
.af-hero-badge {
  display: inline-block;
  background: rgba(255,255,255,.15);
  color: #fff;
  font-size: .75rem;
  font-weight: 600;
  letter-spacing: .05em;
  text-transform: uppercase;
  padding: .15rem .55rem;
  border-radius: 100px;
}
.af-hero-meta { display: none; }
.af-hero-meta-item { display: none; }
.af-hero-meta-label { display: none; }
.af-hero-meta-value { display: none; }

/* ── Pipeline stepper ─────────────────────────────────────────────────── */
.af-stepper {
  display: flex;
  align-items: flex-start;
  gap: 0;
  margin: .5rem 0;
  overflow-x: auto;
  padding-bottom: .25rem;
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
  font-size: .85rem;
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
  font-size: .75rem;
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
  font-size: .8rem;
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
  font-size: .82rem;
  font-weight: 700;
  color: var(--ocean-blue);
}
.af-gallery-compliance {
  font-size: .78rem;
  color: var(--charcoal-mid);
  margin-top: .15rem;
}
.af-badge {
  display: inline-block;
  font-size: .75rem;
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
  font-size: .8rem;
  text-transform: uppercase;
  letter-spacing: .07em;
  color: var(--charcoal-mid);
  margin-bottom: .3rem;
  font-weight: 600;
}
.af-metric-value {
  font-size: 1.6rem;
  font-weight: 700;
  color: var(--ocean-blue);
  line-height: 1;
  margin-bottom: .25rem;
}
.af-metric-sub {
  font-size: .8rem;
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
  font-size: .9rem;
  font-weight: 600;
}
.af-approval-header.approved { background: #EAFAF1; color: var(--success); }
.af-approval-header.rejected { background: #FDEDEC; color: var(--danger); }
.af-approval-header.pending  { background: #FEF9E7; color: var(--warning); }

/* ── Brief builder wizard ─────────────────────────────────────────────── */
.af-wizard-steps {
  display: flex;
  gap: 0;
  margin-bottom: .75rem;
  border-bottom: 2px solid var(--sandy-beige);
}
.af-wizard-step {
  flex: 1;
  text-align: center;
  padding: .75rem .5rem;
  font-size: .88rem;
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
  margin: .75rem 0 .5rem;
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
  font-size: .85rem;
  color: rgba(255,255,255,.82) !important;
  border-left: 3px solid var(--shell-tan);
}

/* ── Campaign brief preview card ──────────────────────────────────────── */
.af-brief-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: .5rem 2rem;
  font-size: .95rem;
}
.af-brief-label {
  color: var(--charcoal-mid);
  font-size: .82rem;
  text-transform: uppercase;
  letter-spacing: .06em;
  font-weight: 600;
}
.af-brief-value {
  color: var(--charcoal);
  font-weight: 500;
  margin-bottom: .5rem;
}

/* ── Text inputs & text areas ─────────────────────────────────────────── */
.stTextInput > div > div > input,
.stTextArea > div > div > textarea {
  border: 1.5px solid var(--sandy-beige) !important;
  border-radius: var(--radius-sm) !important;
  font-size: 0.95rem !important;
  padding: 0.5rem 0.75rem !important;
  transition: border-color var(--transition) !important;
}
.stTextInput > div > div > input:focus,
.stTextArea > div > div > textarea:focus {
  border-color: var(--ocean-light) !important;
  box-shadow: 0 0 0 2px rgba(46,134,193,.12) !important;
}
/* ── Selectbox ────────────────────────────────────────────────────────── */
.stSelectbox > div > div {
  border: 1.5px solid var(--sandy-beige) !important;
  border-radius: var(--radius-sm) !important;
  font-size: 0.95rem !important;
}
/* ── Divider ─────────────────────────────────────────────────────────── */
hr { border-color: var(--sandy-beige) !important; margin: 1.25rem 0 !important; }

/* ── Empty state helper text ─────────────────────────────────────────── */
.af-empty-state {
  text-align: center;
  padding: 2.5rem 1.5rem;
  color: var(--charcoal-mid);
}
.af-empty-state-icon { font-size: 2.5rem; margin-bottom: 0.5rem; }
.af-empty-state-title { font-size: 1.1rem; font-weight: 700; color: var(--charcoal); margin-bottom: 0.3rem; }
.af-empty-state-desc { font-size: 0.95rem; max-width: 420px; margin: 0 auto; line-height: 1.6; }
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
        st.info("No pipeline runs yet this session.")
        return
    entries = log[:3]
    cols = st.columns(len(entries))
    for col, entry in zip(cols, entries):
        with col:
            st.markdown(
                f'<div class="af-card">'
                f'<div class="af-brief-label">Campaign</div>'
                f'<div class="af-brief-value">{entry["campaign"]}</div>'
                f'<div class="af-brief-label">Result</div>'
                f'<div class="af-brief-value">{entry["created"]} creatives · {entry["elapsed"]}</div>'
                f'<div class="af-brief-label">Efficiency</div>'
                f'<div class="af-brief-value">saved {entry["time_saved"]}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_BRIEFS = {
    "Coastal Collection 2025 (Blue Beach House Designs)": "sample_briefs/beach_house_campaign.yaml",
    "Holiday Glow 2025 (LuxeBeauty)": "sample_briefs/holiday_campaign.yaml",
}

DEFAULT_BUILDER_PRODUCTS = [
    {
        "id": "resort-shell-handbag",
        "name": "Resort Shell Handbag",
        "description": "Handcrafted rattan handbag adorned with natural seashells and floral accents, featuring a lined interior, drawstring closure, and room for all your essentials",
        "keywords": "shell handbag, rattan bag, coastal fashion, beach accessory, resort wear, handcrafted, seashell",
    },
    {
        "id": "cowrie-shell-box",
        "name": "Bespoke Rattan Cowrie Shell Box",
        "description": "Hand-woven rattan keepsake box embellished with cowrie shells and turquoise accents, perfect for jewelry storage or coastal home decor",
        "keywords": "cowrie shell, rattan box, keepsake box, coastal decor, jewelry box, handwoven",
    },
    {
        "id": "painted-shell-art",
        "name": "Painted Shell Art",
        "description": "Vibrant hand-painted seashell collection displayed in a gilded bamboo frame, featuring pastel rainbow scallops, starfish, and sand dollars",
        "keywords": "shell art, wall art, coastal wall decor, painted shells, framed art, pastel decor",
    },
]

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

def render_hero_header(title: str, subtitle: str, compact: bool = False, meta: list[tuple[str, str]] | None = None, badge: str = ""):
    if compact:
        st.markdown(
            f'<div class="af-hero" style="padding:.5rem 1.2rem;margin-bottom:.3rem">'
            f'<h1 style="font-size:1.1rem !important">🎨 {title}</h1>'
            f'</div>',
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
    render_target = target or st
    render_target.markdown(
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


def _place_logo_on_canvas(canvas, logo_path: str | None) -> "PILImage":
    """Place logo in top-right corner of a canvas (mirrors Compositor._place_logo)."""
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


def _render_ab_comparison(brief, sample_hero_path: Path | None = None):
    from PIL import Image as PILImage

    if sample_hero_path is None or not sample_hero_path.exists():
        st.info("No hero image available for A/B preview. Run the pipeline first or provide a hero asset.")
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
                canvas = _place_logo_on_canvas(canvas, logo_path)
                st.image(canvas.convert("RGB"), caption=f"{info['icon']} {info['label']}", use_container_width=True)
            except Exception as e:
                st.error(f"{info['label']}: {e}")

        auto = auto_select_template(ratio.ratio, brief.products[0].keywords, brief.message)
        if template == auto:
            with col:
                st.success("Auto-selected")


def _render_brief_builder():
    from src.models import CampaignBrief, Product, AspectRatio, BrandGuidelines

    tab1, tab2, tab3, tab4 = st.tabs(["Campaign", "Brand", "Products", "Review & Run"])
    brief = None

    with tab1:
        col1, col2 = st.columns(2)
        with col1:
            st.session_state.bb_name     = st.text_input("Campaign Name",    value=st.session_state.get("bb_name", "My Campaign 2025"))
            st.session_state.bb_brand    = st.text_input("Brand Name",       value=st.session_state.get("bb_brand", "Blue Beach House Designs"))
            st.session_state.bb_msg      = st.text_area("Campaign Message",  value=st.session_state.get("bb_msg", "Handcrafted coastal elegance for your home"), height=80)
            st.session_state.bb_tagline  = st.text_input("Tagline (optional)", value=st.session_state.get("bb_tagline", ""))
        with col2:
            st.session_state.bb_region   = st.text_input("Target Region",    value=st.session_state.get("bb_region", "Southern Florida — Naples & Palm Beach"))
            st.session_state.bb_audience = st.text_input("Target Audience",  value=st.session_state.get("bb_audience", "Home decor designers, interior stylists, ages 30-60"))
            st.session_state.bb_theme    = st.text_input("Theme",            value=st.session_state.get("bb_theme", "warm coastal"))
            st.session_state.bb_langs    = st.multiselect("Languages", ["en", "es", "fr", "de", "pt", "ja", "zh", "ko"], default=st.session_state.get("bb_langs", ["en"]))

    with tab2:
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

    with tab3:
        num_products = st.number_input("Number of Products", min_value=2, max_value=10, value=st.session_state.get("bb_nprods", 3), key="bb_nprods")

        products_data = []
        for i in range(int(num_products)):
            default_product = DEFAULT_BUILDER_PRODUCTS[i] if i < len(DEFAULT_BUILDER_PRODUCTS) else {
                "id": f"product-{i + 1}",
                "name": f"Product {i + 1}",
                "description": "A beautiful handcrafted coastal product",
                "keywords": "handcrafted, coastal, design",
            }
            with st.expander(f"📦 Product {i + 1}", expanded=(i < 2)):
                pc1, pc2 = st.columns(2)
                with pc1:
                    p_name = st.text_input("Product Name", value=st.session_state.get(f"bb_pname_{i}", default_product["name"]), key=f"bb_pname_{i}")
                    p_id   = st.text_input("Product ID (lowercase, hyphens)", value=st.session_state.get(f"bb_pid_{i}", default_product["id"]), key=f"bb_pid_{i}")
                with pc2:
                    p_desc = st.text_area("Description", value=st.session_state.get(f"bb_pdesc_{i}", default_product["description"]), key=f"bb_pdesc_{i}", height=68)
                    p_kw   = st.text_input("Keywords (comma-separated)", value=st.session_state.get(f"bb_pkw_{i}", default_product["keywords"]), key=f"bb_pkw_{i}")
                product_entry = {"id": p_id.strip(), "name": p_name.strip(), "description": p_desc.strip(), "keywords": [k.strip() for k in p_kw.split(",") if k.strip()]}
                hero_image = default_product.get("hero_image")
                if hero_image:
                    product_entry["hero_image"] = hero_image
                products_data.append(product_entry)

        st.session_state.bb_products_data = products_data

    with tab4:
        brief_dict = {
            "name":     st.session_state.get("bb_name", "My Campaign"),
            "brand":    st.session_state.get("bb_brand", "Brand"),
            "message":  st.session_state.get("bb_msg", ""),
            "tagline":  st.session_state.get("bb_tagline") or None,
            "target_region":   st.session_state.get("bb_region", ""),
            "target_audience": st.session_state.get("bb_audience", ""),
            "theme": st.session_state.get("bb_theme") or None,
            "languages": st.session_state.get("bb_langs", ["en"]),
            "brand_guidelines": {
                "primary_colors": [
                    st.session_state.get("bb_c1", "#1B4F72").upper(),
                    st.session_state.get("bb_c2", "#F5E6CA").upper(),
                    st.session_state.get("bb_c3", "#FFFFFF").upper(),
                ],
                "accent_color":    st.session_state.get("bb_accent", "#D4A574").upper(),
                "font_family":     st.session_state.get("bb_font", "Georgia"),
                "logo_path":       "input_assets/logo.png" if Path("input_assets/logo.png").exists() else None,
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
            return None

        # Brief card preview
        meta_left  = [("Brand", brief.brand), ("Campaign", brief.name), ("Message", brief.message)]
        meta_right = [("Region", brief.target_region), ("Audience", brief.target_audience), ("Theme", brief.theme or "—"), ("Products", str(len(brief.products)))]
        rows = "".join(
            f'<div><div class="af-brief-label">{l}</div><div class="af-brief-value">{v}</div></div>'
            for (l, v) in meta_left + meta_right
        )
        st.markdown(f'<div class="af-card"><div class="af-brief-grid">{rows}</div></div>', unsafe_allow_html=True)

        total = len(brief.products) * 3 * len(brief.languages)
        st.success(f"Ready to generate **{total} creatives** — {len(brief.aspect_ratios)} ratios × {len(brief.products)} products × {len(brief.languages)} language(s)")

        # --- Run Pipeline controls ---
        st.markdown("<div style='height:0.75rem'></div>", unsafe_allow_html=True)
        action_col, options_col, template_col = st.columns([0.9, 1.1, 1.1])
        with action_col:
            st.markdown("<div style='height:1.8rem'></div>", unsafe_allow_html=True)
            run_pipeline_now = st.button("🚀 Run Pipeline", type="primary", use_container_width=True, key="main_run_pipeline")
        with options_col:
            provider_choice = st.selectbox(
                "Image Provider",
                ["mock", "gemini", "firefly", "dalle", "auto"],
                help="Mock = no API key. Gemini = Imagen 4.0. Firefly = Adobe Firefly Services.",
                key="main_provider_choice",
            )
        with template_col:
            template_options = ["auto"] + [template.value for template in LayoutTemplate]
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


def _score_asset(asset: dict) -> float:
    """Score a creative for AI-pick ranking. Higher = better."""
    score = 50.0  # base
    brand = asset.get("brand_compliance", {}).get("status", "not_checked")
    legal = asset.get("legal_compliance", {}).get("status", "not_checked")
    hero  = asset.get("hero_status", "generated")
    ratio = asset.get("aspect_ratio", "")

    # Compliance boosts
    if brand == "passed": score += 20
    elif brand == "warning": score += 5
    elif brand == "failed": score -= 15
    if legal == "passed": score += 20
    elif legal == "warning": score += 5
    elif legal == "failed": score -= 15

    # Generated heroes are unique; reused are less novel
    if hero == "generated": score += 10

    # Prefer versatile ratios (1:1 is most universal)
    if "1:1" in ratio: score += 5
    elif "9:16" in ratio: score += 3

    # Vary by file size as a proxy for visual richness
    fp = asset.get("file_path", "")
    if fp and Path(fp).exists():
        size_kb = Path(fp).stat().st_size / 1024
        score += min(10, size_kb / 50)  # up to 10 pts for larger files

    return score


def _render_gallery(assets: list[dict], base_dir: Path | None = None):
    products: dict[str, list] = {}
    for asset in assets:
        pid = asset["product_id"]
        if pid not in products:
            products[pid] = []
        products[pid].append(asset)

    # AI-pick: find best creative per product
    ai_picks: dict[str, int] = {}
    for pid, passets in products.items():
        scored = [(i, _score_asset(a)) for i, a in enumerate(passets)]
        best_idx, _ = max(scored, key=lambda x: x[1])
        ai_picks[pid] = id(passets[best_idx])  # use object id to match

    for product_id, product_assets in products.items():
        friendly_name = product_id.replace("-", " ").title()
        st.markdown(f'<div class="af-gallery-product-title">📦 {friendly_name}</div>', unsafe_allow_html=True)

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
                is_ai_pick   = id(asset) == ai_picks.get(product_id)

                with col:
                    if is_ai_pick:
                        st.markdown(
                            '<div style="background:linear-gradient(135deg,#FFF3D0,#FFEAA7);color:#8B6914;'
                            'text-align:center;padding:0.35rem;border-radius:8px 8px 0 0;font-size:0.85rem;font-weight:700;'
                            'border:1px solid #E8B849;border-bottom:none">'
                            '⭐ AI Pick</div>',
                            unsafe_allow_html=True,
                        )
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

        st.markdown("<div style='height:1rem'></div>", unsafe_allow_html=True)


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

    # --- Status color map ---
    STATUS_COLORS = {
        "pending":  {"bg": "#FEF3E2", "border": "#E8B849", "text": "#8B6914", "badge": "#F4D03F", "icon": "⏳"},
        "approved": {"bg": "#E8F5E9", "border": "#4CAF50", "text": "#2E7D32", "badge": "#66BB6A", "icon": "✅"},
        "rejected": {"bg": "#FFEBEE", "border": "#EF5350", "text": "#C62828", "badge": "#EF5350", "icon": "❌"},
    }

    # --- Progress bar + summary strip ---
    approved_pct = approved / total * 100 if total else 0
    rejected_pct = rejected / total * 100 if total else 0
    pending_pct  = pending / total * 100 if total else 0
    st.markdown(f"""
    <div style="background:var(--warm-ivory);border:1px solid var(--sandy-beige);border-radius:var(--radius-md);
                padding:1rem 1.2rem;margin-bottom:1rem">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.6rem;flex-wrap:wrap;gap:0.5rem">
        <div style="font-size:1.05rem;font-weight:700;color:var(--charcoal)">
          Review Progress — <span style="color:var(--ocean-blue)">{pct_done:.0f}%</span> complete
        </div>
        <div style="display:flex;gap:1rem;font-size:0.88rem">
          <span style="color:{STATUS_COLORS['pending']['text']}">⏳ {pending} pending</span>
          <span style="color:{STATUS_COLORS['approved']['text']}">✅ {approved} approved</span>
          <span style="color:{STATUS_COLORS['rejected']['text']}">❌ {rejected} rejected</span>
        </div>
      </div>
      <div style="height:8px;border-radius:4px;background:#E0D5C7;overflow:hidden;display:flex">
        <div style="width:{approved_pct}%;background:#4CAF50;transition:width 0.3s"></div>
        <div style="width:{rejected_pct}%;background:#EF5350;transition:width 0.3s"></div>
        <div style="width:{pending_pct}%;background:#F4D03F;transition:width 0.3s"></div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # --- Bulk action buttons (compact row) ---
    b1, b2, b3, spacer = st.columns([1, 1, 1, 3])
    if b1.button("✅ Approve All", key=f"approve_all_{session_key}", use_container_width=True):
        for i in range(len(assets)):
            approvals[i]["status"] = "approved"
        st.rerun()
    if b2.button("❌ Reject All", key=f"reject_all_{session_key}", use_container_width=True):
        for i in range(len(assets)):
            approvals[i]["status"] = "rejected"
        st.rerun()
    if b3.button("🔄 Reset All", key=f"reset_all_{session_key}", use_container_width=True):
        for i in range(len(assets)):
            approvals[i]["status"] = "pending"
            approvals[i]["comment"] = ""
        st.rerun()

    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)

    # --- Per-asset review cards (rows of 3) ---
    for row_start in range(0, len(assets), 3):
        row_assets = list(enumerate(assets))[row_start:row_start + 3]
        cols = st.columns(3)
        for col, (i, asset) in zip(cols, row_assets):
            pid    = asset.get("product_id", "unknown")
            ratio  = asset.get("aspect_ratio", "?")
            lang   = asset.get("language", "?")
            status = approvals[i]["status"]
            sc     = STATUS_COLORS[status]

            brand  = asset.get("brand_compliance", {}).get("status", "not_checked")
            legal  = asset.get("legal_compliance", {}).get("status", "not_checked")
            hero   = asset.get("hero_status", "generated")

            # Friendly product name
            product_name = pid.replace("-", " ").title()

            with col:
                # Card open — colored left border + subtle background
                st.markdown(f"""
                <div style="background:{sc['bg']};border-left:4px solid {sc['border']};
                            border-radius:var(--radius-sm);padding:0.7rem 0.8rem;margin-bottom:0.4rem;
                            box-shadow:var(--shadow-sm)">
                  <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:0.3rem">
                    <span style="font-size:0.92rem;font-weight:700;color:var(--charcoal)">{product_name}</span>
                    <span style="background:{sc['badge']};color:#fff;padding:2px 8px;border-radius:10px;
                                 font-size:0.75rem;font-weight:600;text-transform:uppercase">
                      {sc['icon']} {status}
                    </span>
                  </div>
                  <div style="font-size:0.82rem;color:var(--charcoal-mid);margin-bottom:0.2rem">
                    {ratio} · {lang.upper()}
                    <span style="margin-left:0.5rem">
                      {COMPLIANCE_EMOJI.get(brand,'—')} Brand
                      {COMPLIANCE_EMOJI.get(legal,'—')} Legal
                    </span>
                  </div>
                  <div style="font-size:0.78rem;color:var(--charcoal-light)">
                    {'♻️ Reused hero' if hero == 'reused' else '✦ AI-generated hero'}
                  </div>
                </div>
                """, unsafe_allow_html=True)

                # Image
                fp = asset.get("file_path", "")
                if fp and Path(fp).exists():
                    st.image(fp, use_container_width=True)
                else:
                    st.warning("Image not available")

                # Decision radio
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

                # Comment field
                approvals[i]["comment"] = st.text_input(
                    "Note",
                    value=approvals[i]["comment"],
                    key=f"comment_{session_key}_{i}",
                    placeholder="Add reviewer note…",
                    label_visibility="collapsed",
                )

                # Visual spacer between card rows
                st.markdown("<div style='height:0.3rem'></div>", unsafe_allow_html=True)

    # --- Export section ---
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    exp_col1, exp_col2, _ = st.columns([1.5, 1.5, 3])
    with exp_col1:
        if st.button("📋 Export Manifest", key=f"export_{session_key}", use_container_width=True):
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


def _render_performance(assets: list[dict], session_key: str = "default"):
    if not assets:
        st.info("No assets to analyze.")
        return

    perf = build_performance_report(assets)

    # Light warm palette — consistent with rest of app
    BG_CREAM    = "var(--warm-ivory)"
    CARD_BG     = "#FFF9F2"
    BORDER      = "var(--sandy-beige)"
    OCEAN       = "var(--ocean-blue)"
    SAND        = "var(--shell-tan)"
    CHARCOAL    = "var(--charcoal)"
    CHARCOAL_M  = "var(--charcoal-mid)"
    GREEN       = "#2E7D32"
    RED         = "#C62828"
    GOLD_BG     = "#FFF3D0"
    GOLD_BORDER = "#E8B849"
    GOLD_TEXT   = "#8B6914"
    ROW_ALT     = "rgba(212,165,116,0.06)"
    ROW_WINNER  = "rgba(232,184,73,0.12)"

    sorted_kpis = sorted(perf.kpis, key=lambda x: x.cpa)
    winner_id = perf.winner.creative_id if perf.winner else None

    # ── Summary metric cards ──
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:0.8rem;margin-bottom:1rem">
      <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:var(--radius-sm);padding:0.8rem 1rem;text-align:center">
        <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.05em;color:{CHARCOAL_M};margin-bottom:0.2rem">Total Spend</div>
        <div style="font-size:1.3rem;font-weight:700;color:{CHARCOAL}">${perf.total_spend:,.0f}</div>
      </div>
      <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:var(--radius-sm);padding:0.8rem 1rem;text-align:center">
        <div style="font-size:0.78rem;text-transform:uppercase;letter-spacing:0.05em;color:{CHARCOAL_M};margin-bottom:0.2rem">Impressions</div>
        <div style="font-size:1.3rem;font-weight:700;color:{CHARCOAL}">{perf.total_impressions/1000:.1f}K</div>
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
    """, unsafe_allow_html=True)

    # ── Winner banner ──
    if perf.winner:
        w = perf.winner
        ctr_delta = ((w.ctr - perf.avg_ctr) / perf.avg_ctr * 100) if perf.avg_ctr else 0
        cpa_delta = ((perf.avg_cpa - w.cpa) / perf.avg_cpa * 100) if perf.avg_cpa else 0
        st.markdown(f"""
        <div style="background:{GOLD_BG};border-left:4px solid {GOLD_BORDER};border-radius:var(--radius-sm);
                    padding:0.8rem 1.2rem;margin-bottom:1rem;display:flex;align-items:center;gap:0.8rem;flex-wrap:wrap">
          <span style="font-size:1.4rem">🏆</span>
          <div>
            <div style="font-size:1rem;font-weight:700;color:{GOLD_TEXT}">Top Performer — {w.creative_id.replace("-"," ").title()}</div>
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
        """, unsafe_allow_html=True)

    # ── KPI Table ──
    table_rows = ""
    for idx, k in enumerate(sorted_kpis):
        is_winner = k.creative_id == winner_id
        bg = ROW_WINNER if is_winner else (ROW_ALT if idx % 2 == 0 else "transparent")
        badge = '<span style="background:#E8B849;color:#fff;padding:1px 6px;border-radius:8px;font-size:0.72rem;margin-left:0.3rem">BEST</span>' if is_winner else ""
        ctr_color = GREEN if k.ctr > perf.avg_ctr else CHARCOAL
        cpa_color = GREEN if k.cpa < perf.avg_cpa else CHARCOAL
        table_rows += (
            f'<tr style="background:{bg}">'
            f'<td style="padding:0.45rem 0.6rem;font-weight:{"700" if is_winner else "400"}">{k.creative_id}{badge}</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.product_id.replace("-"," ").title()}</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.aspect_ratio}</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.language.upper()}</td>'
            f'<td style="padding:0.45rem 0.6rem">${k.spend_usd:.0f}</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.impressions:,}</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.clicks:,}</td>'
            f'<td style="padding:0.45rem 0.6rem;color:{ctr_color};font-weight:600">{k.ctr:.2f}%</td>'
            f'<td style="padding:0.45rem 0.6rem">{k.conversions}</td>'
            f'<td style="padding:0.45rem 0.6rem;color:{cpa_color};font-weight:600">${k.cpa:.2f}</td>'
            f'</tr>'
        )

    st.markdown(f"""
    <div style="background:{CARD_BG};border:1px solid {BORDER};border-radius:var(--radius-sm);padding:1rem;overflow-x:auto">
      <div style="font-size:0.95rem;font-weight:700;color:{CHARCOAL};margin-bottom:0.6rem">Per-Creative Performance Indicators</div>
      <table style="width:100%;border-collapse:collapse;font-size:0.88rem;color:{CHARCOAL}">
        <thead>
          <tr style="border-bottom:2px solid {BORDER}">
            {''.join(f'<th style="padding:0.45rem 0.6rem;text-align:left;color:{SAND};font-weight:700;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.04em">{h}</th>' for h in ["Creative","Product","Ratio","Lang","Spend","Impressions","Clicks","Click-Through Rate","Conversions","Cost Per Acq."])}
          </tr>
        </thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>
    """, unsafe_allow_html=True)

    # ── Export ──
    st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
    csv_data   = [f"{k.creative_id},{k.product_id},{k.aspect_ratio},{k.language},{k.spend_usd:.2f},{k.impressions},{k.clicks},{k.conversions},{k.ctr:.2f},{k.cpa:.2f},{k.cpc:.2f}" for k in perf.kpis]
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


def _analysis_to_payload(analysis) -> dict:
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


def _estimate_time_saved_hours(created_count: int, elapsed_seconds: float) -> float:
    """Use the same manual-vs-automated assumption everywhere in the UI."""
    return max(0, (created_count * 15 - elapsed_seconds / 60) / 60)


def _build_campaign_summary_cards(
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
        {"label": "Total Assets", "value": str(total_assets), "sub": "creatives planned", "icon": "📁", "bar_pct": 100},
        {"label": "Created", "value": str(created_count), "sub": created_sub, "icon": "✅", "bar_pct": created_count / max(total_assets, 1) * 100},
        {"label": "Heroes Reused", "value": str(hero_reused_count), "sub": "cached images", "icon": "♻️"},
        {"label": "Failed", "value": str(failed_count), "sub": "need attention", "icon": "⚠️"},
        {"label": "Duration", "value": f"{elapsed_seconds:.1f}s", "sub": "total pipeline time", "icon": "⏱️"},
        {"label": "Time Saved", "value": f"{time_saved_hours:.1f}h", "sub": "vs. manual workflow", "icon": "🚀"},
    ]


def _render_brief_review(brief):
    """Render a compact brief review panel before pipeline execution."""
    rows = "".join(
        f'<div><div class="af-brief-label">{label}</div><div class="af-brief-value">{value}</div></div>'
        for label, value in [
            ("Brand", brief.brand),
            ("Campaign", brief.name),
            ("Message", brief.message),
            ("Region", brief.target_region),
            ("Audience", brief.target_audience),
            ("Theme", brief.theme or "—"),
            ("Languages", ", ".join(brief.languages)),
            ("Products", str(len(brief.products))),
        ]
    )
    st.markdown(f'<div class="af-card"><div class="af-brief-grid">{rows}</div></div>', unsafe_allow_html=True)

    total = len(brief.products) * len(brief.aspect_ratios) * len(brief.languages)
    st.info(
        f"Ready to generate **{total} creatives** "
        f"({len(brief.aspect_ratios)} aspect ratios × {len(brief.products)} products × {len(brief.languages)} languages)."
    )

    render_section_title("Pipeline Overview")
    render_pipeline_stepper(active_stage=0)

    render_section_title("Brief Analysis")
    _render_analysis(_analysis_to_payload(analyze_brief(brief)))

    render_section_title("Products")
    for product in brief.products:
        with st.expander(f"📦 {product.name}"):
            col_left, col_right = st.columns(2)
            with col_left:
                st.markdown(f"**ID:** `{product.id}`")
                st.markdown(f"**Description:** {product.description}")
            with col_right:
                hero_text = "Will be generated via GenAI" if not product.hero_image else f"Existing: `{product.hero_image}`"
                st.markdown(f"**Hero Image:** {hero_text}")
                if product.keywords:
                    st.markdown(f"**Keywords:** {', '.join(product.keywords)}")


def _serialize_result_assets(result) -> list[dict]:
    """Prepare assets for gallery and approval queue rendering."""
    assets = []
    for asset in result.assets:
        data = asset.model_dump()
        data["hero_status"] = data["hero_status"].value if hasattr(data["hero_status"], "value") else data["hero_status"]
        if data.get("brand_compliance") and hasattr(data["brand_compliance"].get("status", ""), "value"):
            data["brand_compliance"]["status"] = data["brand_compliance"]["status"].value
        if data.get("legal_compliance") and hasattr(data["legal_compliance"].get("status", ""), "value"):
            data["legal_compliance"]["status"] = data["legal_compliance"]["status"].value
        assets.append(data)
    return assets


def _normalize_report_asset_paths(assets: list[dict], campaign_dir: Path) -> list[dict]:
    """Convert report-relative asset paths into on-disk paths the UI can open."""
    normalized = []
    for asset in assets:
        patched = dict(asset)
        original = Path(patched["file_path"])
        if not original.exists():
            parts = original.parts
            if parts and parts[0] == "sample_output":
                patched["file_path"] = str(ROOT / original)
            else:
                patched["file_path"] = str(campaign_dir / Path(*parts[1:]))
        normalized.append(patched)
    return normalized


def _render_pipeline_results(brief, result):
    """Render the post-run tabs and summary for a completed pipeline."""
    # This view is the shared "what happened?" surface after a successful run.
    time_saved_hrs = _estimate_time_saved_hours(result.created_count, result.elapsed_seconds)
    assets_data = _serialize_result_assets(result)

    tab_campaign, tab_approval, tab_ab, tab_analytics = st.tabs(
        ["Campaign", "Approval", "Variations", "Analytics"]
    )

    with tab_campaign:
        render_metric_cards(_build_campaign_summary_cards(
            total_assets=result.total_assets,
            created_count=result.created_count,
            hero_reused_count=result.hero_reused_count,
            failed_count=result.failed_count,
            elapsed_seconds=result.elapsed_seconds,
            time_saved_hours=time_saved_hrs,
            created_sub="successfully done",
        ))
        if result.warnings:
            with st.expander(f"⚠️ Warnings ({len(result.warnings)})"):
                for warning in result.warnings:
                    st.warning(warning)

    with tab_approval:
        _render_approval_queue(assets_data, session_key="pipeline_run")

    with tab_ab:
        st.markdown(
            '<div style="color:var(--charcoal-mid);font-size:0.92rem;margin-bottom:0.5rem">'
            'Compare all 5 layout templates side-by-side using the generated hero images.</div>',
            unsafe_allow_html=True,
        )
        from src.storage import StorageManager as _SM, slugify as _slugify
        storage = _SM(input_dir=Path("input_assets"), output_dir=Path("output"))
        for product in brief.products:
            st.markdown(f"**{product.name}**")
            hero_dir = storage.get_campaign_dir(brief.name) / _slugify(product.id)
            hero_candidates = list(hero_dir.rglob("hero*.png")) + list(hero_dir.rglob("hero*.jpg"))
            if hero_candidates:
                _render_ab_comparison(brief, hero_candidates[0])
            else:
                st.info(f"No hero found for {product.name}")
            st.divider()

    with tab_analytics:
        _render_performance(assets_data, session_key="pipeline_run")
        from src.storage import StorageManager
        storage = StorageManager(input_dir=Path("input_assets"), output_dir=Path("output"))
        campaign_dir = storage.get_campaign_dir(brief.name)
        report = _load_sample_report(campaign_dir)
        if report:
            _render_metrics(report)
        else:
            st.info("Metrics available in the JSON report.")


def _render_sample_library():
    """Render pre-generated sample outputs as a secondary discovery section."""
    sample_base = ROOT / "sample_output"
    campaigns = _find_sample_campaigns(sample_base)

    if not campaigns:
        st.info("No pre-generated samples found in `sample_output/`.")
        return

    selected_name = st.selectbox(
        "Sample campaign",
        [campaign.name.replace("_", " ").title() for campaign in campaigns],
        key="sample_library_select",
    )
    selected_idx = [campaign.name.replace("_", " ").title() for campaign in campaigns].index(selected_name)
    campaign_dir = campaigns[selected_idx]
    report = _load_sample_report(campaign_dir)

    if not report:
        st.info("No report found for the selected sample campaign.")
        return

    # Sample reports are stored as JSON, so file paths may need to be re-rooted.
    sample_tabs = st.tabs(["Campaign", "Approval", "Variations", "Analytics"])
    patched_assets = _normalize_report_asset_paths(report.get("assets", []), campaign_dir)

    with sample_tabs[0]:
        elapsed = report.get("elapsed_seconds", 0)
        efficiency = report.get("efficiency", {})
        render_metric_cards(_build_campaign_summary_cards(
            total_assets=report["total_assets"],
            created_count=report["created_count"],
            hero_reused_count=report["hero_reused_count"],
            failed_count=report["failed_count"],
            elapsed_seconds=elapsed,
            time_saved_hours=efficiency.get("time_saved_hours", 0),
            created_sub="successfully composed",
        ))
        analysis_data = report.get("brief_analysis")
        if analysis_data:
            render_section_title("Brief Analysis")
            _render_analysis(analysis_data)

    with sample_tabs[1]:
        _render_approval_queue(patched_assets, session_key=f"sample_{selected_idx}")

    with sample_tabs[2]:
        try:
            brief_for_ab = None
            for _, brief_path in SAMPLE_BRIEFS.items():
                try:
                    candidate = load_brief(brief_path)
                    if candidate.name.lower().replace(" ", "_") in campaign_dir.name:
                        brief_for_ab = candidate
                        break
                except Exception:
                    continue

            if brief_for_ab:
                hero_candidates = list(campaign_dir.rglob("hero*.png")) + list(campaign_dir.rglob("hero*.jpg"))
                if not hero_candidates:
                    hero_candidates = list(campaign_dir.rglob("*.jpg"))
                _render_ab_comparison(brief_for_ab, hero_candidates[0] if hero_candidates else None)
            else:
                st.info("Could not match a campaign brief for A/B comparison.")
        except Exception as exc:
            st.warning(f"A/B comparison unavailable: {exc}")

    with sample_tabs[3]:
        _render_performance(patched_assets, session_key=f"sample_{selected_idx}")
        _render_metrics(report)


def _save_uploaded_brief(uploaded) -> str:
    """Persist an uploaded brief under an ignored per-session directory."""
    safe_name   = Path(uploaded.name).name
    session_dir = _create_temp_brief_dir()
    dest = session_dir / safe_name
    if not dest.resolve().is_relative_to(session_dir.resolve()):
        raise ValueError("Invalid filename")
    dest.write_bytes(uploaded.getvalue())
    return str(dest)


def _create_temp_brief_dir() -> Path:
    """Create an ignored workspace for transient brief files."""
    session_dir = ROOT / "temp_brief_upload" / uuid.uuid4().hex[:8]
    session_dir.mkdir(parents=True, exist_ok=True)
    return session_dir


def _save_generated_brief_yaml(brief) -> str:
    """Persist a built brief to the ignored temp upload area."""
    import tempfile
    import yaml as _yaml

    session_dir = _create_temp_brief_dir()
    brief_yaml = _yaml.dump(
        {"campaign": brief.model_dump(exclude_none=True)},
        default_flow_style=False,
    )
    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".yaml",
        delete=False,
        dir=str(session_dir),
    ) as handle:
        handle.write(brief_yaml)
        return handle.name


# ---------------------------------------------------------------------------
# Main content
# ---------------------------------------------------------------------------

if "active_run_result" not in st.session_state:
    st.session_state.active_run_result = None
if "active_run_brief" not in st.session_state:
    st.session_state.active_run_brief = None
if "active_run_campaign" not in st.session_state:
    st.session_state.active_run_campaign = None
if "active_run_provider" not in st.session_state:
    st.session_state.active_run_provider = "mock"
if "nav_page" not in st.session_state:
    st.session_state.nav_page = "brief"

# ---------------------------------------------------------------------------
# Sidebar — Narrow icon navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    # Logo / brand mark at top
    st.markdown(
        '<div style="text-align:center;padding:0.6rem 0 0.3rem">'
        '<span style="font-size:1.6rem">🎨</span>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="af-nav-divider"></div>', unsafe_allow_html=True)

    # Nav: Build Brief
    is_brief = st.session_state.nav_page == "brief"
    st.markdown(
        f'<div class="af-nav-item {"active" if is_brief else ""}">'
        f'<div class="af-nav-icon">📝</div>'
        f'<div class="af-nav-label">Build<br>Brief</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button("📝 Brief", key="nav_brief", use_container_width=True):
        st.session_state.nav_page = "brief"
        st.rerun()

    # Nav: Results
    has_results = st.session_state.active_run_result is not None
    is_results = st.session_state.nav_page == "results"
    st.markdown(
        f'<div class="af-nav-item {"active" if is_results else ""}">'
        f'<div class="af-nav-icon">{"✅" if has_results else "🚀"}</div>'
        f'<div class="af-nav-label">{"Results" if has_results else "Run"}<br>Pipeline</div>'
        f'</div>',
        unsafe_allow_html=True,
    )
    if st.button("🚀 Run" if not has_results else "✅ Results", key="nav_results", use_container_width=True):
        st.session_state.nav_page = "results"
        st.rerun()

    # Bottom spacer + version
    st.markdown(
        '<div style="position:fixed;bottom:0.8rem;left:0;width:88px;text-align:center">'
        '<div class="af-nav-divider"></div>'
        '<div style="font-size:0.55rem;color:rgba(255,255,255,.4);padding-top:0.3rem">AdForge v1.0</div>'
        '</div>',
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Hero header (compact)
# ---------------------------------------------------------------------------
_has_results = st.session_state.active_run_result is not None
render_hero_header(
    "AdForge",
    "Build briefs. Generate creatives. Review and approve — all in one place.",
    compact=_has_results,
    badge="Pipeline Studio",
)

# ---------------------------------------------------------------------------
# Page: Build Brief
# ---------------------------------------------------------------------------
if st.session_state.nav_page == "brief":
    current_brief = _render_brief_builder()
    current_brief_path = None

    if current_brief is not None and st.session_state.get("_run_triggered"):
        st.session_state._run_triggered = False
        provider_choice = st.session_state.get("main_provider_choice", "mock")
        template_choice = st.session_state.get("main_template_choice", "auto")

        run_brief_path = current_brief_path
        if run_brief_path is None:
            run_brief_path = _save_generated_brief_yaml(current_brief)

            forced_template = None if template_choice == "auto" else template_choice
            status_col, stepper_col = st.columns([0.2, 0.8])
            stepper_slot = stepper_col.empty()
            status_slot = status_col.empty()
            render_pipeline_stepper(active_stage=1, target=stepper_slot)

            with status_slot.status("Running pipeline...", expanded=True) as status:
                try:
                    result = run_pipeline(
                        brief_path=run_brief_path,
                        input_dir="input_assets",
                        output_dir="output",
                        mock=(provider_choice == "mock"),
                        provider_type=None if provider_choice == "auto" else provider_choice,
                        template=forced_template,
                        status_callback=lambda msg: status.update(label=msg),
                    )
                    status.update(label="Pipeline Complete!", state="complete", expanded=False)
                    render_pipeline_stepper(done_stages=7, target=stepper_slot)
                    st.session_state.active_run_result = result
                    st.session_state.active_run_brief = current_brief
                    st.session_state.active_run_campaign = current_brief.name
                    st.session_state.active_run_provider = provider_choice
                    time_saved_hrs = _estimate_time_saved_hours(
                        result.created_count,
                        result.elapsed_seconds,
                    )
                    _log_run(
                        campaign=current_brief.name,
                        provider=provider_choice,
                        total=result.total_assets,
                        created=result.created_count,
                        failed=result.failed_count,
                        elapsed=result.elapsed_seconds,
                        time_saved_hrs=time_saved_hrs,
                    )
                    # Auto-switch to results page
                    st.session_state.nav_page = "results"
                    st.session_state._pipeline_reran = True
                    st.rerun()
                except RuntimeError as exc:
                    status.update(label="Pipeline Failed", state="error", expanded=False)
                    st.error(f"Pipeline failed: {exc}")

# ---------------------------------------------------------------------------
# Page: Results
# ---------------------------------------------------------------------------
if st.session_state.nav_page == "results":
    if (
        st.session_state.active_run_result is not None
        and st.session_state.active_run_campaign
    ):
        _render_pipeline_results(
            st.session_state.active_run_brief,
            st.session_state.active_run_result,
        )
    else:
        st.markdown(
            '<div class="af-empty-state">'
            '<div class="af-empty-state-icon">🚀</div>'
            '<div class="af-empty-state-title">No results yet</div>'
            '<div class="af-empty-state-desc">Head to <strong>Build Brief</strong> to configure your campaign, '
            'then hit <strong>Run Pipeline</strong> on the Review & Run tab.</div>'
            '</div>',
            unsafe_allow_html=True,
        )
