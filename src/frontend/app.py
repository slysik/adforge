"""
AdForge Web UI — Streamlit frontend for the creative automation pipeline.

Business Value:
  Enables stakeholders (creative directors, campaign managers) to build
  briefs, run the pipeline, and approve assets interactively — no CLI
  or code knowledge required. Serves as the primary demo surface.

Purpose:
  Provide a full-featured web UI for brief building, pipeline execution
  with real-time progress, creative gallery, approval queue, and
  analytics dashboard.

Description:
  Key sections (driven by st.session_state.nav_page):
    - Brief Builder: upload YAML or build manually with form inputs
    - Pipeline Runner: 7-stage stepper with real-time progress
    - Results Gallery: assets organized by product and aspect ratio
    - Approval Queue: review, comment, approve/reject individual assets
    - Analytics Dashboard: KPI cards, performance metrics, provider stats
    - Sample Library: pre-built briefs for quick demos

  Launch with: streamlit run src/frontend/app.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import streamlit as st

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)

from src.frontend.app_components import (  # noqa: E402
    estimate_time_saved_hours,
    log_run,
    render_hero_header,
    render_pipeline_stepper,
)
from src.frontend.app_pages import (  # noqa: E402
    render_brief_builder,
    render_pipeline_results,
    save_generated_brief_yaml,
)
from src.backend.pipeline import run_pipeline  # noqa: E402

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
# Inject CSS from external stylesheet
# ---------------------------------------------------------------------------
_CSS_PATH = Path(__file__).parent / "app_styles.css"
st.markdown(f"<style>{_CSS_PATH.read_text()}</style>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Session state initialization
# ---------------------------------------------------------------------------
if "run_log" not in st.session_state:
    st.session_state.run_log = []
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
if "pipeline_done_stages" not in st.session_state:
    st.session_state.pipeline_done_stages = 0

# ---------------------------------------------------------------------------
# Sidebar — Narrow icon navigation
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown(
        '<div style="text-align:center;padding:0.6rem 0 0.3rem">'
        '<span style="font-size:1.6rem">🎨</span>'
        "</div>",
        unsafe_allow_html=True,
    )
    st.markdown('<div class="af-nav-divider"></div>', unsafe_allow_html=True)

    # Nav: Build Brief
    if st.button("📝 Build Brief", key="nav_brief", use_container_width=True):
        st.session_state.nav_page = "brief"
        st.rerun()

    # Nav: Results
    has_results = st.session_state.active_run_result is not None
    results_label = "✅ Results" if has_results else "🚀 Run Pipeline"
    if st.button(results_label, key="nav_results", use_container_width=True):
        st.session_state.nav_page = "results"
        st.rerun()

    # Bottom spacer + version
    st.markdown(
        '<div style="position:fixed;bottom:0.8rem;left:0;width:88px;text-align:center">'
        '<div class="af-nav-divider"></div>'
        '<div style="font-size:0.55rem;color:rgba(255,255,255,.4);padding-top:0.3rem">AdForge v1.0</div>'
        "</div>",
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Hero header (compact when results exist)
# ---------------------------------------------------------------------------
_has_results = st.session_state.active_run_result is not None
render_hero_header(
    "AdForge",
    "Build briefs. Generate creatives. Review and approve — all in one place.",
    compact=_has_results,
)

# ---------------------------------------------------------------------------
# Page: Build Brief
# ---------------------------------------------------------------------------
if st.session_state.nav_page == "brief":
    current_brief = render_brief_builder()
    current_brief_path = None

    # ── Pipeline execution gate ──────────────────────────────────────
    if current_brief is not None and st.session_state.get("_run_triggered"):
        st.session_state._run_triggered = False
        provider_choice = st.session_state.get("main_provider_choice", "mock")
        template_choice = st.session_state.get("main_template_choice", "auto")

        run_brief_path = current_brief_path
        if run_brief_path is None:
            run_brief_path = save_generated_brief_yaml(current_brief)

            forced_template = None if template_choice == "auto" else template_choice
            status_col, stepper_col = st.columns([0.2, 0.8])
            stepper_slot = stepper_col.empty()
            status_slot = status_col.empty()
            render_pipeline_stepper(active_stage=1, target=stepper_slot)

            with status_slot.status("Running pipeline...", expanded=True) as status:
                try:
                    result = run_pipeline(
                        brief_path=run_brief_path,
                        input_dir="data/input_assets",
                        output_dir="output",
                        mock=(provider_choice == "mock"),
                        provider_type=(
                            None if provider_choice == "auto" else provider_choice
                        ),
                        template=forced_template,
                        status_callback=lambda msg: status.update(label=msg),
                    )
                    status.update(
                        label="Pipeline Complete!",
                        state="complete",
                        expanded=False,
                    )
                    render_pipeline_stepper(done_stages=7, target=stepper_slot)
                    st.session_state.pipeline_done_stages = 7
                    st.session_state.active_run_result = result
                    st.session_state.active_run_brief = current_brief
                    st.session_state.active_run_campaign = current_brief.name
                    st.session_state.active_run_provider = provider_choice
                    time_saved_hrs = estimate_time_saved_hours(
                        result.created_count,
                        result.elapsed_seconds,
                    )
                    log_run(
                        campaign=current_brief.name,
                        provider=provider_choice,
                        total=result.total_assets,
                        created=result.created_count,
                        failed=result.failed_count,
                        elapsed=result.elapsed_seconds,
                        time_saved_hrs=time_saved_hrs,
                    )
                    st.session_state.nav_page = "results"
                    st.session_state._pipeline_reran = True
                    st.rerun()
                except RuntimeError as exc:
                    status.update(
                        label="Pipeline Failed", state="error", expanded=False
                    )
                    st.error(f"Pipeline failed: {exc}")

# ---------------------------------------------------------------------------
# Page: Results
# ---------------------------------------------------------------------------
elif st.session_state.nav_page == "results":
    if (
        st.session_state.active_run_result is not None
        and st.session_state.active_run_campaign
    ):
        if st.session_state.pipeline_done_stages > 0:
            render_pipeline_stepper(done_stages=st.session_state.pipeline_done_stages)
        render_pipeline_results(
            st.session_state.active_run_brief,
            st.session_state.active_run_result,
        )
    else:
        st.markdown(
            '<div class="af-empty-state">'
            '<div class="af-empty-state-icon">🚀</div>'
            '<div class="af-empty-state-title">No results yet</div>'
            '<div class="af-empty-state-desc">Head to <strong>Build Brief</strong> to configure your campaign, '
            "then hit <strong>Run Pipeline</strong> on the Review & Run tab.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
