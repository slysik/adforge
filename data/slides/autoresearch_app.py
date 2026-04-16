#!/usr/bin/env python3
"""
App.py Modular Architecture Slide — Autoresearch Optimization.

Karpathy autoresearch pattern for a single slide showing the app.py
modularization into 4 files: app.py (orchestrator), app_components.py
(widgets), app_pages.py (renderers), app_styles.css (design system).

24-point grading rubric (6 criteria x 4 points) designed to prove to
an interviewer that you deeply understand the code.

Usage:
    python3 data/slides/autoresearch_app.py              # Continuous loop
    python3 data/slides/autoresearch_app.py --once       # Single cycle
    python3 data/slides/autoresearch_app.py --cycles 5   # Run N cycles
    python3 data/slides/autoresearch_app.py --reset      # Reset state + single cycle
"""

from __future__ import annotations

import argparse
import json
import os
import shutil as _shutil
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

GEMINI_KEY = os.getenv("NANO_BANANA_API_KEY") or os.getenv("GEMINI_API_KEY")

GEN_MODEL = "gemini-3.1-flash-image-preview"
EVAL_MODEL = "gemini-2.5-flash"
CLAUDE_BIN = _shutil.which("claude") or "/Users/slysik/.local/bin/claude"
CLAUDE_CLI_MODEL = os.getenv("CLAUDE_CLI_MODEL", "sonnet")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASE_DIR = PROJECT_ROOT / "data" / "autoresearch_app"
PROMPT_FILE = BASE_DIR / "prompt.txt"
BEST_PROMPT_FILE = BASE_DIR / "best_prompt.txt"
FAILURES_MEMORY_FILE = BASE_DIR / "failures_memory.json"
STATE_FILE = BASE_DIR / "state.json"
RESULTS_FILE = BASE_DIR / "results.jsonl"
SLIDES_DIR = BASE_DIR / "slides"

BATCH_SIZE = 1
NUM_CRITERIA = 6
MAX_SCORE = NUM_CRITERIA * 4  # 24
CYCLE_SECONDS = 120

# ─── Slide Definition ─────────────────────────────────────────────────────────

SLIDE = {
    "id": "app_modular_architecture",
    "title": "Streamlit UI: Modular Architecture",
    "description": (
        "Architecture slide showing how the AdForge Streamlit UI is structured "
        "as a modular system — NOT a monolith. Rich hand-drawn sketchnote "
        "illustration with bold marker fonts, hand-drawn pictogram icons, "
        "dashed rough-edged borders, soft pastel watercolor fills. NOT a wireframe. "
        "\n\n"
        "TITLE: 'Streamlit UI: Modular Architecture' — bold marker text at top-left, NO box around title. "
        "Subtitle below in smaller marker: 'From 2,423 lines to 4 focused modules'. "
        "\n\n"
        "LAYOUT: Two-zone layout. "
        "TOP ZONE: Four module boxes in a single horizontal row, left-to-right, connected by import arrows. "
        "BOTTOM ZONE: A full-width horizontal banner showing the Streamlit runtime context. "
        "\n\n"
        "THE FOUR MODULE BOXES (left to right): "
        "\n"
        "BOX 1 (light coral/salmon fill #ffc9c9, dashed border, TALLEST — this is the entry point): "
        "Header: 'app.py' in bold marker with a rocket/play icon. "
        "Subheader: '240 lines — Orchestrator' in smaller text. "
        "Below, FOUR bullet items with small icons: "
        "  gear icon — 'Page config + CSS injection', "
        "  database icon — 'Session state init (7 keys)', "
        "  compass icon — 'Sidebar navigation (2 pages)', "
        "  lightning icon — 'Pipeline execution gate'. "
        "A small annotation below: 'st.set_page_config must be first Streamlit call'. "
        "\n"
        "RIGHT-ARROW from Box 1 to Box 2, labeled 'imports'. "
        "\n"
        "BOX 2 (light green fill #b2f2bb, dashed border): "
        "Header: 'app_components.py' in bold marker with a puzzle-piece icon. "
        "Subheader: '407 lines — Widgets + Constants' in smaller text. "
        "Below, FOUR bullet items with small icons: "
        "  grid icon — 'render_metric_cards()', "
        "  steps icon — 'render_pipeline_stepper()', "
        "  star icon — 'score_asset() — AI Pick ranking', "
        "  list icon — 'TEMPLATE_INFO, PIPELINE_STAGES'. "
        "\n"
        "RIGHT-ARROW from Box 2 to Box 3, labeled 'imports'. "
        "\n"
        "BOX 3 (light purple fill #d0bfff, dashed border): "
        "Header: 'app_pages.py' in bold marker with a browser/window icon. "
        "Subheader: '1,034 lines — Page Renderers' in smaller text. "
        "Below, FOUR bullet items with small icons: "
        "  form icon — 'render_brief_builder() — 4-tab wizard + import', "
        "  check icon — 'render_approval_queue() — review cards', "
        "  chart icon — 'render_performance() — KPI table', "
        "  image icon — 'render_pipeline_results() — post-run'. "
        "\n"
        "BOX 4 (light blue fill #a5d8ff, dashed border, slightly shorter — no code logic): "
        "Header: 'app_styles.css' in bold marker with a paintbrush icon. "
        "Subheader: '742 lines — Design System' in smaller text. "
        "Below, THREE bullet items with small icons: "
        "  palette icon — 'CSS custom properties (brand tokens)', "
        "  layout icon — 'Component classes (.af-card, .af-hero)', "
        "  eye icon — 'Streamlit overrides (tabs, buttons, sidebar)'. "
        "Small annotation: 'Raw CSS — IDE syntax highlighting + linting'. "
        "\n\n"
        "IMPORT ARROWS: "
        "A dashed arrow from Box 1 (app.py) curving DOWN to Box 4 (app_styles.css) labeled 'reads file'. "
        "A dashed arrow from Box 3 (app_pages.py) LEFT to Box 2 (app_components.py) labeled 'imports'. "
        "These show the dependency graph: app.py → app_pages.py → app_components.py, "
        "and app.py reads app_styles.css. No circular dependencies. "
        "\n\n"
        "BOTTOM BANNER (light yellow fill #fff3bf, dashed border, full width): "
        "Gear icon + bold text: 'Streamlit Runtime — full rerun on every interaction'. "
        "Three annotations inside: "
        "  'st.session_state persists across reruns (7 keys)', "
        "  'Python module cache — imports resolve once', "
        "  'st.set_page_config() must be first call'. "
        "\n\n"
        "KEY DESIGN ANNOTATIONS (small italic text near relevant boxes): "
        "Near Box 1: 'Thin orchestrator — routing + execution only'. "
        "Near Box 3: 'Heaviest module — all user-facing rendering'. "
        "Near the import arrows: 'No circular imports — leaf dependency graph'. "
        "\n\n"
        "All arrows point RIGHT or DOWN only. NO diagonal, curved upward, or circular arrows. "
        "NO hub-and-spoke layout. Clean left-to-right primary flow. "
        "All text must be clearly readable at presentation distance (30pt+ equivalent)."
    ),
}

# ─── 24-Point Grading Rubric (6 criteria x 4 points) ────────────────────────

EVAL_PROMPT = """You are evaluating a modular architecture presentation slide for a software engineering interview. The slide shows a Streamlit app split into 4 modules. Score STRICTLY against these 6 criteria.

SCORING: Each criterion is scored 0-4:
  4 = Excellent — fully meets the criterion with no issues
  3 = Good — meets criterion with minor issues
  2 = Fair — partially meets criterion, noticeable issues
  1 = Poor — mostly fails criterion
  0 = Fail — does not meet criterion at all

Criteria:

1. LEGIBILITY (0-4): ALL text is clearly readable — no garbled, overlapping, blurry, or cut-off text. All words are real English words spelled correctly. Font size appears large enough to present (30pt+ equivalent). File names spelled correctly: app.py, app_components.py, app_pages.py, app_styles.css. Key terms spelled correctly: Streamlit, session_state, Pydantic, Pillow, ThreadPoolExecutor, render_metric_cards, render_pipeline_stepper, render_brief_builder, render_approval_queue.

2. CORRECTNESS (0-4): The module responsibilities are accurately represented. app.py is the orchestrator (page config, session state, nav, routing). app_components.py contains reusable widgets and constants. app_pages.py contains page-level renderers including brief import. app_styles.css contains CSS. Line counts are approximately correct (app.py ~240, app_components.py ~407, app_pages.py ~1034, app_styles.css ~742). Import direction is correct: app.py imports from app_pages and app_components; app_pages imports from app_components. No circular dependencies shown.

3. SOLUTION_ARCH_BEST_PRACTICES (0-4): Demonstrates proper separation of concerns: thin orchestrator pattern, CSS extracted from Python, reusable widgets separated from page-specific renderers. Dependency graph is clearly acyclic (no circular imports). The Streamlit runtime context (session state, rerun semantics) is acknowledged. Module boundaries follow natural seam lines (constants, widgets, pages, styles). This looks like a diagram a senior engineer would draw.

4. SIMPLICITY (0-4): A new engineer could understand the module split in under 30 seconds. The diagram is not cluttered — it shows the essential structure without overwhelming detail. Module names and their responsibilities are immediately clear. The visual hierarchy is obvious (title → module boxes → supporting details). Function names shown are the most important ones, not an exhaustive list.

5. CODE_KNOWLEDGE (0-4): The slide demonstrates that the presenter deeply understands the codebase — not just high-level boxes. Specific evidence of depth: exact line counts, key function names (render_metric_cards, render_brief_builder, score_asset), awareness of Streamlit constraints (set_page_config must be first, 7 session_state keys, rerun semantics), the import dependency direction, and why CSS is a raw file (IDE support). An interviewer would believe this person wrote and refactored this code.

6. VISUAL_DESIGN (0-4): Uses soft pastel colors consistently. Professional and polished — suitable for an interview. Clean alignment and spacing between elements. Arrows are consistent in style and direction. The overall aesthetic is cohesive — warm hand-drawn sketchnote style. NOT a raw wireframe or ugly diagram. Color coding is meaningful (each module has a distinct color).

Respond in this exact JSON format ONLY — no markdown, no explanation, just the JSON:
{"legibility": 4, "correctness": 4, "solution_arch": 4, "simplicity": 4, "code_knowledge": 4, "visual_design": 4, "total": 24, "failures": []}

Be strict but fair. Deduct points for specific issues. Add brief descriptions to the failures array for any criterion scoring below 4."""

# ─── Mutation Prompt ──────────────────────────────────────────────────────────

MUTATION_TEMPLATE = """You are optimizing a text-to-image prompt for generating a modular architecture diagram slide. The prompt is sent to Gemini's image generation model. Your goal: modify the STYLE/RULES portion so the generated slide consistently scores 24/24.

CURRENT PROMPT:
---
{current_prompt}
---

LAST RESULT ({score}/{max_score}):
- Legibility:      {leg}/4
- Correctness:     {cor}/4
- Sol. Arch:       {sol}/4
- Simplicity:      {sim}/4
- Code Knowledge:  {cod}/4
- Visual Design:   {vis}/4

FAILURES:
{failures}

PERSISTENT FAILURES (recurring across {total_runs} runs):
{recurring_failures}

BEST SCORE SO FAR: {best_score}/{max_score}

RULES FOR YOUR MODIFICATION:
- Keep the hand-drawn sketchnote aesthetic
- PRIORITY: Address PERSISTENT FAILURES first
- For spelling failures: add explicit "MUST spell X correctly, NEVER write Y" rules
- For layout failures: add stronger directional constraints
- For correctness failures: reinforce exact module names, line counts, and responsibilities
- For code_knowledge failures: ensure specific function names, Streamlit constraints, and design rationale are visible
- Be specific and imperative — image models respond to direct commands
- Keep prompt under 800 words
- Return ONLY the new prompt text — no explanation, no markdown fences"""

# ─── Helpers ──────────────────────────────────────────────────────────────────


def load_failures_memory() -> dict:
    if FAILURES_MEMORY_FILE.exists():
        return json.loads(FAILURES_MEMORY_FILE.read_text())
    return {"failure_counts": {}, "total_runs": 0}


def update_failures_memory(eval_result: dict):
    memory = load_failures_memory()
    memory["total_runs"] += 1
    counts = memory["failure_counts"]
    for fail in eval_result.get("failures", []):
        if fail == "eval_error":
            continue
        counts[fail] = counts.get(fail, 0) + 1
    memory["failure_counts"] = dict(
        sorted(counts.items(), key=lambda x: x[1], reverse=True)
    )
    FAILURES_MEMORY_FILE.write_text(json.dumps(memory, indent=2))
    return memory


def top_recurring_failures(top_n: int = 10) -> tuple[str, int]:
    memory = load_failures_memory()
    counts = memory["failure_counts"]
    total = memory["total_runs"]
    if not counts:
        return "- None yet", total
    lines = []
    for fail, count in list(counts.items())[:top_n]:
        pct = int(count / max(total, 1) * 100)
        lines.append(f"  ({count}/{total} runs, {pct}%) {fail}")
    return "\n".join(lines), total


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"best_score": -1, "run_number": 0}


def save_state(state: dict):
    STATE_FILE.write_text(json.dumps(state, indent=2))


def load_prompt() -> str:
    return PROMPT_FILE.read_text().strip()


def save_prompt(prompt: str):
    PROMPT_FILE.write_text(prompt)


# ─── Generation ───────────────────────────────────────────────────────────────


def generate_slide(gemini_client, prompt: str, output_path: Path) -> bool:
    """Generate the app.py architecture slide via Gemini image generation."""
    from google.genai import types

    full_prompt = (
        f"{prompt}\n\n"
        f"FORMAT: 16:9 landscape orientation. Fill the FULL WIDTH of a wide horizontal canvas. "
        f"Content must span edge-to-edge horizontally. Do NOT leave large empty margins.\n\n"
        f"SPELLING GUARD — render these EXACTLY:\n"
        f"  - 'app.py' 'app_components.py' 'app_pages.py' 'app_styles.css'\n"
        f"  - 'render_metric_cards' 'render_pipeline_stepper' 'render_brief_builder'\n"
        f"  - 'render_approval_queue' 'render_performance' 'score_asset'\n"
        f"  - 'render_pipeline_results' 'render_ab_comparison'\n"
        f"  - 'Streamlit' 'session_state' 'st.set_page_config'\n"
        f"  - 'TEMPLATE_INFO' 'PIPELINE_STAGES'\n\n"
        f"--- SLIDE TO CREATE ---\n"
        f"{SLIDE['title']}\n"
        f"Content & Layout: {SLIDE['description']}"
    )
    try:
        response = gemini_client.models.generate_content(
            model=GEN_MODEL,
            contents=full_prompt,
            config=types.GenerateContentConfig(
                response_modalities=["IMAGE", "TEXT"],
            ),
        )
        for part in response.candidates[0].content.parts:
            if part.inline_data:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                output_path.write_bytes(part.inline_data.data)
                # Resize to 1920x1080
                try:
                    from PIL import Image as PilImage

                    TARGET_W, TARGET_H = 1920, 1080
                    img = PilImage.open(output_path).convert("RGB")
                    img_w, img_h = img.size
                    scale = min(TARGET_W / img_w, TARGET_H / img_h)
                    new_w, new_h = int(img_w * scale), int(img_h * scale)
                    img = img.resize((new_w, new_h), PilImage.LANCZOS)
                    canvas = PilImage.new(
                        "RGB", (TARGET_W, TARGET_H), (255, 255, 255)
                    )
                    canvas.paste(
                        img, ((TARGET_W - new_w) // 2, (TARGET_H - new_h) // 2)
                    )
                    canvas.save(output_path)
                except Exception as e:
                    print(f"    [resize warning]: {e}")
                return True
        return False
    except Exception as e:
        print(f"    GEN ERROR: {e}")
        return False


# ─── Evaluation ───────────────────────────────────────────────────────────────


def evaluate_slide(gemini_client, image_path: Path) -> dict | None:
    """Evaluate slide against 6 criteria via Gemini vision. Returns scores dict."""
    from google.genai import types

    image_bytes = image_path.read_bytes()
    try:
        response = gemini_client.models.generate_content(
            model=EVAL_MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
                EVAL_PROMPT,
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
            ),
        )
        text = response.text.strip()
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        result = json.loads(text)
        result["total"] = (
            result.get("legibility", 0)
            + result.get("correctness", 0)
            + result.get("solution_arch", 0)
            + result.get("simplicity", 0)
            + result.get("code_knowledge", 0)
            + result.get("visual_design", 0)
        )
        return result
    except Exception as e:
        print(f"    EVAL ERROR: {e}")
        return None


# ─── Mutation ─────────────────────────────────────────────────────────────────


def mutate_prompt(
    current_prompt: str,
    eval_result: dict,
    best_score: int,
    recurring_failures: str = "- None yet",
    total_runs: int = 0,
) -> str:
    """Use Claude CLI to improve the prompt based on failure analysis."""
    import subprocess

    failures_text = (
        "\n".join(f"  - {f}" for f in eval_result.get("failures", [])) or "- None"
    )

    prompt_text = MUTATION_TEMPLATE.format(
        current_prompt=current_prompt,
        score=eval_result.get("total", 0),
        max_score=MAX_SCORE,
        leg=eval_result.get("legibility", 0),
        cor=eval_result.get("correctness", 0),
        sol=eval_result.get("solution_arch", 0),
        sim=eval_result.get("simplicity", 0),
        cod=eval_result.get("code_knowledge", 0),
        vis=eval_result.get("visual_design", 0),
        failures=failures_text,
        best_score=best_score,
        recurring_failures=recurring_failures,
        total_runs=total_runs,
    )

    clean_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    result = subprocess.run(
        [CLAUDE_BIN, "-p", "--model", CLAUDE_CLI_MODEL, prompt_text],
        capture_output=True,
        text=True,
        timeout=180,
        cwd="/tmp",
        env=clean_env,
    )
    if result.returncode != 0 or not result.stdout.strip():
        print(f"    MUTATE ERROR: {result.stderr[:200]}")
        return current_prompt
    return result.stdout.strip()


# ─── Main Cycle ───────────────────────────────────────────────────────────────


def run_cycle(gemini_client, state: dict) -> dict:
    """Run one autoresearch optimization cycle."""
    run_num = state["run_number"] + 1
    state["run_number"] = run_num
    run_dir = SLIDES_DIR / f"run_{run_num:03d}"
    run_dir.mkdir(parents=True, exist_ok=True)

    prompt = load_prompt()

    print(f"\n{'=' * 60}")
    print(
        f"RUN {run_num} | {datetime.now().strftime('%H:%M:%S')} | Best: {state['best_score']}/{MAX_SCORE}"
    )
    print(f"{'=' * 60}")

    # ── Generate ──────────────────────────────────────────────────
    print("\n  Generating slide...")
    out_path = run_dir / f"{SLIDE['id']}.png"
    ok = generate_slide(gemini_client, prompt, out_path)

    if not ok:
        print("  ERROR: Slide generation failed. Skipping cycle.")
        save_state(state)
        return state

    print(f"  Generated: {out_path}")

    # ── Evaluate ──────────────────────────────────────────────────
    print("\n  Evaluating against 24-point rubric...")
    result = evaluate_slide(gemini_client, out_path)

    if not result:
        result = {
            "legibility": 0,
            "correctness": 0,
            "solution_arch": 0,
            "simplicity": 0,
            "code_knowledge": 0,
            "visual_design": 0,
            "total": 0,
            "failures": ["eval_error"],
        }

    score = result["total"]

    print(f"\n  SCORE: {score}/{MAX_SCORE}")
    print(f"    Legibility:      {result.get('legibility', 0)}/4")
    print(f"    Correctness:     {result.get('correctness', 0)}/4")
    print(f"    Solution Arch:   {result.get('solution_arch', 0)}/4")
    print(f"    Simplicity:      {result.get('simplicity', 0)}/4")
    print(f"    Code Knowledge:  {result.get('code_knowledge', 0)}/4")
    print(f"    Visual Design:   {result.get('visual_design', 0)}/4")

    if result.get("failures"):
        print("\n  FAILURES:")
        for f in result["failures"]:
            print(f"    - {f}")

    # ── Log ───────────────────────────────────────────────────────
    log_entry = {
        "run": run_num,
        "timestamp": datetime.now().isoformat(),
        "score": score,
        "max": MAX_SCORE,
        "criteria": {
            "legibility": result.get("legibility", 0),
            "correctness": result.get("correctness", 0),
            "solution_arch": result.get("solution_arch", 0),
            "simplicity": result.get("simplicity", 0),
            "code_knowledge": result.get("code_knowledge", 0),
            "visual_design": result.get("visual_design", 0),
        },
        "failures": result.get("failures", []),
        "prompt_len": len(prompt),
    }
    with open(RESULTS_FILE, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # ── Update failure memory ─────────────────────────────────────
    update_failures_memory(result)
    recurring, total_runs = top_recurring_failures()
    if total_runs > 1:
        print(f"\n  TOP RECURRING FAILURES (across {total_runs} runs):")
        for line in recurring.split("\n")[:5]:
            print(f"  {line}")

    # ── Keep or discard ───────────────────────────────────────────
    if score > state["best_score"]:
        old_best = state["best_score"]
        state["best_score"] = score
        BEST_PROMPT_FILE.write_text(prompt)
        print(f"\n  NEW BEST! {score}/{MAX_SCORE} (was {old_best})")

        best_slide = BASE_DIR / "best_slide.png"
        _shutil.copy2(out_path, best_slide)
        print(f"  Saved to: {best_slide}")
    else:
        print(f"\n  No improvement ({score} vs best {state['best_score']})")

    # ── Mutate ────────────────────────────────────────────────────
    if score < MAX_SCORE:
        print("\n  Mutating prompt...")
        base_prompt = (
            BEST_PROMPT_FILE.read_text().strip()
            if BEST_PROMPT_FILE.exists()
            else prompt
        )
        new_prompt = mutate_prompt(
            base_prompt,
            result,
            state["best_score"],
            recurring,
            total_runs,
        )
        save_prompt(new_prompt)
        preview = new_prompt[:200].replace("\n", " ")
        print(f"  New prompt ({len(new_prompt)} chars): {preview}...")
    else:
        print(f"\n  PERFECT {MAX_SCORE}/{MAX_SCORE}! Prompt fully optimized.")

    save_state(state)
    return state


# ─── Initial Prompt ───────────────────────────────────────────────────────────

INITIAL_PROMPT = """Create a rich hand-drawn sketchnote illustration on a clean white background. Style: professional illustrator with bold markers — hand-lettered text with natural pen imperfections, small hand-drawn pictogram icons (rocket=orchestrator, puzzle=components, window=pages, paintbrush=styles, gear=runtime, lightning=execution), dashed rough-edged borders on boxes, soft pastel watercolor fills. NOT a wireframe. NOT flat digital. Warm, illustrated, hand-crafted technical diagram feel.

CONTEXT: AdForge — a Streamlit web app for creative automation. The monolithic app.py (2,423 lines total) was refactored into 4 focused modules. This slide shows the modular architecture for a technical interview — proving deep code knowledge.

COLORS:
- app.py box: light coral (#ffc9c9) — entry point / orchestrator.
- app_components.py box: light green (#b2f2bb) — reusable widgets.
- app_pages.py box: light purple (#d0bfff) — page renderers.
- app_styles.css box: light blue (#a5d8ff) — design system.
- Bottom runtime banner: light yellow (#fff3bf).
- All text: dark (#1e1e1e). No bright/saturated fills.

TITLE RULE: Slide title = plain bold marker text at top-left. NO box around the title.

TEXT CLARITY — HIGHEST PRIORITY: Every character crisp and readable at 30pt+. Generous spacing. NEVER overlap text. File names and function names in smaller text within each module box.

SPECIFIC CONTENT TO SHOW (demonstrates code knowledge):
- app.py (240 lines): Page config, CSS injection, session state init (7 keys including pipeline_done_stages), sidebar nav (2 pages), pipeline execution gate, stepper persistence
- app_components.py (407 lines): render_metric_cards(), render_pipeline_stepper(), render_ab_comparison(), score_asset(), TEMPLATE_INFO, PIPELINE_STAGES constants
- app_pages.py (1,034 lines): render_brief_builder() 4-tab wizard + YAML import, render_approval_queue() review cards, render_performance() KPI table, render_pipeline_results() post-run, save_generated_brief_yaml() to sample_briefs/
- app_styles.css (742 lines): CSS custom properties (brand tokens), .af-card/.af-hero component classes, Streamlit overrides (tabs, buttons, sidebar)
- Bottom banner: Streamlit runtime — session_state persists across reruns (7 keys), module cache, st.set_page_config() must be first call

IMPORT ARROWS — MANDATORY, DRAW ALL FOUR. Each arrow must be visually bold, clearly labeled, and impossible to miss:

1. SOLID ARROW: app.py → app_pages.py. Label: "imports". app.py calls render_brief_builder(), render_pipeline_results(), save_generated_brief_yaml() from app_pages.py. THIS ARROW IS THE PRIMARY DEPENDENCY — draw it prominently.

2. SOLID ARROW: app.py → app_components.py. Label: "imports". app.py directly imports and calls render_hero_header(), render_pipeline_stepper(), estimate_time_saved_hours(), log_run() from app_components.py. THIS ARROW IS REQUIRED — do not omit it.

3. SOLID ARROW: app_pages.py → app_components.py. Label: "imports". Pages call render_metric_cards(), render_section_title(), render_ab_comparison(), build_campaign_summary_cards() from components.

4. DASHED ARROW: app.py → app_styles.css. Label: "injects CSS". app.py ALONE reads and injects the stylesheet via st.markdown(). NO other module touches app_styles.css.

ARROW CHECKLIST — VERIFY BEFORE FINALIZING: (1) app.py→app_pages.py present? (2) app.py→app_components.py present? (3) app_pages.py→app_components.py present? (4) app.py→app_styles.css present? All four must be YES.

CSS OWNERSHIP RULE — ZERO TOLERANCE: ONLY app.py has any arrow to app_styles.css. app_components.py has NO arrow, NO connection, NO reference to app_styles.css. app_pages.py has NO arrow to app_styles.css.

LAYOUT LAW: STRICT left-to-right top row: app.py (leftmost) → app_pages.py (center) → app_components.py (rightmost). app_styles.css sits below app.py only, connected by the dashed arrow downward. Bottom banner spans full width. ALL arrows point RIGHT or DOWN only. NO hub-and-spoke, radial, circular, or fan-out. NO diagonal arrows. NO upward arrows.

ANNOTATIONS (small italic text):
- Near app.py: 'Thin orchestrator — routing + execution only'
- Near app_pages.py: 'Heaviest module — all user-facing rendering'
- Near import arrows: 'No circular imports — leaf dependency graph'

FORBIDDEN — ZERO TOLERANCE:
- NO missing arrow from app.py to app_pages.py
- NO missing arrow from app.py to app_components.py
- NO arrow from app_components.py to app_styles.css
- NO arrow from app_pages.py to app_styles.css
- NO hub-and-spoke, radial, circular, or fan-out arrangements
- NO diagonal arrows, NO upward arrows
- NO step numbers, NO digits indicating sequence
- NO cluttered or overlapping elements"""


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="App.py modular architecture slide autoresearch"
    )
    parser.add_argument("--once", action="store_true", help="Run a single cycle")
    parser.add_argument(
        "--cycles", type=int, default=0, help="Run N cycles (0=infinite)"
    )
    parser.add_argument(
        "--reset", action="store_true", help="Reset state and start fresh"
    )
    args = parser.parse_args()

    if not GEMINI_KEY:
        print(
            "ERROR: NANO_BANANA_API_KEY or GEMINI_API_KEY not set", file=sys.stderr
        )
        sys.exit(1)

    from google import genai

    BASE_DIR.mkdir(parents=True, exist_ok=True)
    SLIDES_DIR.mkdir(parents=True, exist_ok=True)

    if args.reset:
        print("Resetting state...")
        save_state({"best_score": -1, "run_number": 0})
        if RESULTS_FILE.exists():
            RESULTS_FILE.rename(RESULTS_FILE.with_suffix(".jsonl.bak"))
        if FAILURES_MEMORY_FILE.exists():
            FAILURES_MEMORY_FILE.rename(FAILURES_MEMORY_FILE.with_suffix(".json.bak"))

    # Create initial prompt if missing
    if not PROMPT_FILE.exists():
        PROMPT_FILE.write_text(INITIAL_PROMPT)
        print(f"  Created initial prompt: {PROMPT_FILE}")

    gemini_client = genai.Client(api_key=GEMINI_KEY)
    state = load_state()

    print("App.py Modular Architecture — Autoresearch Optimizer")
    print(f"  Gen model:  {GEN_MODEL}")
    print(f"  Eval model: {EVAL_MODEL}")
    print(f"  Rubric:     {NUM_CRITERIA} criteria x 4 points = {MAX_SCORE} max")
    print(f"  State:      run {state['run_number']}, best {state['best_score']}/{MAX_SCORE}")

    if args.once or args.reset:
        run_cycle(gemini_client, state)
        return

    max_cycles = args.cycles or float("inf")
    i = 0
    while i < max_cycles:
        start = time.time()
        try:
            state = run_cycle(gemini_client, state)
        except Exception as e:
            print(f"\n  CYCLE ERROR: {e}")
            traceback.print_exc()
        elapsed = time.time() - start
        i += 1

        if i < max_cycles:
            wait = max(0, CYCLE_SECONDS - elapsed)
            if wait > 0:
                print(f"\n  Waiting {wait:.0f}s until next cycle...")
                time.sleep(wait)

    print(f"\nDone. Best score: {state['best_score']}/{MAX_SCORE}")


if __name__ == "__main__":
    main()
