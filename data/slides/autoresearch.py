#!/usr/bin/env python3
"""
AdForge Solution Architecture Slide — Autoresearch Optimization.

Karpathy autoresearch pattern adapted for a single pipeline-flow slide:
1. Generate slide image via Gemini image gen
2. Evaluate against 6 criteria (24-point rubric) via Gemini vision
3. Compare against best score — keep winner
4. Mutate prompt via Claude CLI to fix failures
5. Repeat every 2 minutes

Usage:
    python3 data/slides/autoresearch.py              # Continuous loop
    python3 data/slides/autoresearch.py --once       # Single cycle
    python3 data/slides/autoresearch.py --cycles 5   # Run N cycles
    python3 data/slides/autoresearch.py --reset      # Reset state + single cycle
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

GEMINI_KEY = os.getenv("NANO_BANANA_API_KEY") or os.getenv("GEMINI_API_KEY")

GEN_MODEL = "gemini-3.1-flash-image-preview"
EVAL_MODEL = "gemini-2.5-flash"
MUTATE_MODEL = "claude-sonnet-4-6"

import shutil as _shutil
CLAUDE_BIN = _shutil.which("claude") or "/Users/slysik/.local/bin/claude"
CLAUDE_CLI_MODEL = os.getenv("CLAUDE_CLI_MODEL", "sonnet")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
BASE_DIR = PROJECT_ROOT / "data" / "autoresearch"
PROMPT_FILE = BASE_DIR / "prompt.txt"
BEST_PROMPT_FILE = BASE_DIR / "best_prompt.txt"
FAILURES_MEMORY_FILE = BASE_DIR / "failures_memory.json"
STATE_FILE = BASE_DIR / "state.json"
RESULTS_FILE = BASE_DIR / "results.jsonl"
SLIDES_DIR = BASE_DIR / "slides"

BATCH_SIZE = 1  # Single slide — we generate 1 variation per cycle
NUM_CRITERIA = 6  # 6 criteria x 4 points each = 24 max
MAX_SCORE = NUM_CRITERIA * 4  # 24
CYCLE_SECONDS = 120

# ─── Slide Definition ─────────────────────────────────────────────────────────

SLIDE = {
    "id": "adforge_pipeline_flow",
    "title": "AdForge: How the Pipeline Works End to End",
    "description": (
        "Solution architecture slide showing the AdForge creative automation pipeline "
        "in a clean, professional diagram style — NOT a wireframe, NOT a screenshot. "
        "Rich hand-drawn sketchnote illustration with bold marker fonts, hand-drawn "
        "pictogram icons, dashed rough-edged borders, soft pastel watercolor fills. "
        "\n\n"
        "TITLE: 'AdForge: How the Pipeline Works End to End' — bold marker text at top-left, NO box around title. "
        "\n\n"
        "LAYOUT: Strict LEFT-TO-RIGHT horizontal flow with right-arrows between each stage. "
        "One horizontal pipeline band spanning the full width of the slide. "
        "\n\n"
        "INPUT (left edge): A box labeled 'Campaign Brief (YAML / JSON)' with a document icon. Pastel orange fill. "
        "\n\n"
        "SEVEN PIPELINE STAGES as boxes in a single horizontal row, connected by right-arrows: "
        "\n"
        "BOX 1 (light blue fill): 'Ingest & Validate' — clipboard/checkmark icon. Below in smaller text: 'models.py — Pydantic'. "
        "BOX 2 (light green fill): 'Analyze Brief' — brain/lightbulb icon. Below: 'analyzer.py — Heuristic (LLM opt-in)'. "
        "BOX 3 (light yellow fill): 'Resolve Cache' — database/magnifier icon. Below: 'storage.py — Hero Reuse'. "
        "BOX 4 (light purple fill): 'Generate Heroes' — magic wand/sparkle icon. Below: 'providers.py — Firefly / Gemini / DALL-E / Mock'. "
        "BOX 5 (light pink fill): 'Compose Creatives' — paint palette/layers icon. Below: 'compositor.py + templates.py — Pillow'. "
        "BOX 6 (light teal fill): 'Validate Compliance' — shield/checkmark icon. Below: 'validator.py — Color + Logo + Legal'. "
        "BOX 7 (light gray fill): 'Report' — chart/dashboard icon. Below: 'report.py — Console + JSON + HTML + ZIP'. "
        "\n\n"
        "OUTPUT (right edge): A box labeled 'Localized Creatives (products x ratios x languages)' with a grid/gallery icon. Pastel orange fill. "
        "\n\n"
        "BELOW THE PIPELINE: A thin horizontal banner spanning the full width labeled "
        "'pipeline.py — 7-Stage Orchestrator with ThreadPoolExecutor' with a gear icon. Light coral/salmon fill. "
        "\n\n"
        "KEY ANNOTATIONS (small text, positioned around relevant stages): "
        "Near Stage 4: 'Parallel via ThreadPoolExecutor' "
        "Near Stage 5: 'Text via Pillow — no AI hallucination' "
        "Near Stage 6: 'Every 10th pixel sampled' "
        "\n\n"
        "All arrows point RIGHT only. NO diagonal, curved, or upward arrows. "
        "NO hub-and-spoke. NO circular layout. Strict left-to-right flow. "
        "All text must be clearly readable at presentation distance (30pt+ equivalent). "
        "Each stage box should be the same height, creating a clean horizontal band."
    ),
}

# ─── 24-Point Grading Rubric (6 criteria x 4 points) ──────────────────────────

EVAL_PROMPT = """You are evaluating a solution architecture presentation slide for an engineering interview. Score STRICTLY against these 6 criteria.

SCORING: Each criterion is scored 0-4:
  4 = Excellent — fully meets the criterion with no issues
  3 = Good — meets criterion with minor issues
  2 = Fair — partially meets criterion, noticeable issues
  1 = Poor — mostly fails criterion
  0 = Fail — does not meet criterion at all

Criteria:

1. LEGIBILITY (0-4): ALL text is clearly readable — no garbled, overlapping, blurry, or cut-off text. All words are real English words spelled correctly. Font size appears large enough to present (30pt+ equivalent). Module names (models.py, pipeline.py, providers.py, compositor.py, templates.py, validator.py, report.py, analyzer.py, storage.py) are spelled correctly. Key terms spelled correctly: Pydantic, Pillow, ThreadPoolExecutor, Firefly, Gemini, DALL-E, YAML, JSON, Heuristic, Compliance.

2. CORRECTNESS (0-4): The pipeline stages are in the CORRECT ORDER: Ingest → Analyze → Resolve Cache → Generate Heroes → Compose Creatives → Validate Compliance → Report. Each stage maps to its correct module. Input is a Campaign Brief (YAML or JSON), output is localized creatives (count depends on brief: products x ratios x languages). The provider chain shows Firefly/Gemini/DALL-E/Mock. Analysis is heuristic by default (LLM opt-in). Validation includes color pixels, logo verification, and legal checker. Reporting includes console, JSON, HTML, and ZIP. No fabricated or incorrect technical details.

3. SOLUTION_ARCH_BEST_PRACTICES (0-4): Follows solution architecture diagramming conventions: clear input on the left, output on the right, processing stages flow left-to-right, each stage labeled with its responsibility, technology/module annotations are present. The orchestrator (pipeline.py) is visible as a cross-cutting concern. The diagram would be appropriate for a technical interview presentation.

4. SIMPLICITY (0-4): A new engineer could understand the pipeline flow in under 30 seconds. The diagram is not cluttered — it shows the essential flow without overwhelming detail. Stage names are concise and descriptive. The visual hierarchy is clear (title → pipeline stages → supporting details). No unnecessary decorative elements that distract from comprehension.

5. VISUAL_DESIGN (0-4): Uses soft pastel colors consistently. Professional and polished — suitable for an interview. Clean alignment and spacing between elements. Arrows are consistent in style and direction. The overall aesthetic is cohesive. NOT a raw wireframe or ugly diagram.

6. LINEAR_LAYOUT (0-4): The pipeline flows in ONE clear direction — strictly left-to-right. Not circular, radial, scattered, hub-and-spoke, or multi-directional. All arrows point right. Input on the left edge, output on the right edge. The 7 stages form a clear horizontal sequence.

Respond in this exact JSON format ONLY — no markdown, no explanation, just the JSON:
{"legibility": 4, "correctness": 4, "solution_arch": 4, "simplicity": 4, "visual_design": 4, "linear_layout": 4, "total": 24, "failures": []}

Be strict but fair. Deduct points for specific issues. Add brief descriptions to the failures array for any criterion scoring below 4."""

# ─── Mutation Prompt ──────────────────────────────────────────────────────────

MUTATION_TEMPLATE = """You are optimizing a text-to-image prompt for generating a solution architecture diagram slide. The prompt is sent to Gemini's image generation model. Your goal: modify the STYLE/RULES portion so the generated slide consistently scores 24/24.

CURRENT PROMPT:
---
{current_prompt}
---

LAST RESULT ({score}/{max_score}):
- Legibility:    {leg}/4
- Correctness:   {cor}/4
- Sol. Arch:     {sol}/4
- Simplicity:    {sim}/4
- Visual Design: {vis}/4
- Linear Layout: {lin}/4

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
- For correctness failures: reinforce the exact stage order and module mappings
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
    """Generate the solution architecture slide via Gemini image generation."""
    from google.genai import types

    full_prompt = (
        f"{prompt}\n\n"
        f"FORMAT: 16:9 landscape orientation. Fill the FULL WIDTH of a wide horizontal canvas. "
        f"Content must span edge-to-edge horizontally. Do NOT leave large empty margins.\n\n"
        f"SPELLING GUARD — render these EXACTLY:\n"
        f"  - 'models.py' 'pipeline.py' 'providers.py' 'compositor.py' 'templates.py'\n"
        f"  - 'validator.py' 'report.py' 'analyzer.py' 'storage.py'\n"
        f"  - 'Pydantic' 'Pillow' 'Firefly' 'Gemini' 'DALL-E' 'ThreadPoolExecutor'\n"
        f"  - 'Heuristic' 'Compliance' 'YAML' 'JSON'\n\n"
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
                    canvas = PilImage.new("RGB", (TARGET_W, TARGET_H), (255, 255, 255))
                    canvas.paste(img, ((TARGET_W - new_w) // 2, (TARGET_H - new_h) // 2))
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
        # Ensure total is computed
        result["total"] = (
            result.get("legibility", 0) +
            result.get("correctness", 0) +
            result.get("solution_arch", 0) +
            result.get("simplicity", 0) +
            result.get("visual_design", 0) +
            result.get("linear_layout", 0)
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

    failures_text = "\n".join(
        f"  - {f}" for f in eval_result.get("failures", [])
    ) or "- None"

    prompt_text = MUTATION_TEMPLATE.format(
        current_prompt=current_prompt,
        score=eval_result.get("total", 0),
        max_score=MAX_SCORE,
        leg=eval_result.get("legibility", 0),
        cor=eval_result.get("correctness", 0),
        sol=eval_result.get("solution_arch", 0),
        sim=eval_result.get("simplicity", 0),
        vis=eval_result.get("visual_design", 0),
        lin=eval_result.get("linear_layout", 0),
        failures=failures_text,
        best_score=best_score,
        recurring_failures=recurring_failures,
        total_runs=total_runs,
    )

    clean_env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
    result = subprocess.run(
        [CLAUDE_BIN, "-p", "--model", CLAUDE_CLI_MODEL, prompt_text],
        capture_output=True, text=True, timeout=180,
        cwd="/tmp", env=clean_env,
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

    print(f"\n{'='*60}")
    print(f"RUN {run_num} | {datetime.now().strftime('%H:%M:%S')} | Best: {state['best_score']}/{MAX_SCORE}")
    print(f"{'='*60}")

    # ── Generate ──────────────────────────────────────────────────
    print(f"\n  Generating slide...")
    out_path = run_dir / f"{SLIDE['id']}.png"
    ok = generate_slide(gemini_client, prompt, out_path)

    if not ok:
        print("  ERROR: Slide generation failed. Skipping cycle.")
        save_state(state)
        return state

    print(f"  Generated: {out_path}")

    # ── Evaluate ──────────────────────────────────────────────────
    print(f"\n  Evaluating against 24-point rubric...")
    result = evaluate_slide(gemini_client, out_path)

    if not result:
        result = {
            "legibility": 0, "correctness": 0, "solution_arch": 0,
            "simplicity": 0, "visual_design": 0, "linear_layout": 0,
            "total": 0, "failures": ["eval_error"],
        }

    score = result["total"]

    print(f"\n  SCORE: {score}/{MAX_SCORE}")
    print(f"    Legibility:      {result.get('legibility', 0)}/4")
    print(f"    Correctness:     {result.get('correctness', 0)}/4")
    print(f"    Solution Arch:   {result.get('solution_arch', 0)}/4")
    print(f"    Simplicity:      {result.get('simplicity', 0)}/4")
    print(f"    Visual Design:   {result.get('visual_design', 0)}/4")
    print(f"    Linear Layout:   {result.get('linear_layout', 0)}/4")

    if result.get("failures"):
        print(f"\n  FAILURES:")
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
            "visual_design": result.get("visual_design", 0),
            "linear_layout": result.get("linear_layout", 0),
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

        # Copy winning slide to top-level for easy access
        best_slide = BASE_DIR / "best_slide.png"
        import shutil
        shutil.copy2(out_path, best_slide)
        print(f"  Saved to: {best_slide}")
    else:
        print(f"\n  No improvement ({score} vs best {state['best_score']})")

    # ── Mutate ────────────────────────────────────────────────────
    if score < MAX_SCORE:
        print("\n  Mutating prompt...")
        base_prompt = BEST_PROMPT_FILE.read_text().strip() if BEST_PROMPT_FILE.exists() else prompt
        new_prompt = mutate_prompt(
            base_prompt, result, state["best_score"],
            recurring, total_runs,
        )
        save_prompt(new_prompt)
        preview = new_prompt[:200].replace("\n", " ")
        print(f"  New prompt ({len(new_prompt)} chars): {preview}...")
    else:
        print(f"\n  PERFECT {MAX_SCORE}/{MAX_SCORE}! Prompt fully optimized.")

    save_state(state)
    return state


# ─── Entry Point ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="AdForge solution arch slide autoresearch")
    parser.add_argument("--once", action="store_true", help="Run a single cycle")
    parser.add_argument("--cycles", type=int, default=0, help="Run N cycles (0=infinite)")
    parser.add_argument("--reset", action="store_true", help="Reset state and start fresh")
    args = parser.parse_args()

    if not GEMINI_KEY:
        print("ERROR: NANO_BANANA_API_KEY or GEMINI_API_KEY not set", file=sys.stderr)
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

    print("AdForge Solution Architecture — Autoresearch Optimizer")
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


# ─── Initial Prompt ───────────────────────────────────────────────────────────

INITIAL_PROMPT = """Create a rich hand-drawn sketchnote illustration on a clean white background. Style: professional illustrator with bold markers — hand-lettered text with natural pen imperfections, small hand-drawn pictogram icons (clipboard=validate, brain=analyze, database=cache, wand=generate, palette=compose, shield=validate, chart=report), dashed rough-edged borders on boxes, soft pastel watercolor fills. NOT a wireframe. NOT flat digital. Warm, illustrated, hand-crafted technical diagram feel.

CONTEXT: AdForge — a creative automation pipeline that transforms a single campaign brief (YAML or JSON) into localized ad creatives (products x ratios x languages) in seconds. This is the solution architecture overview for a technical interview.

COLORS:
- Stage boxes: soft pastels — light blue (#a5d8ff), light green (#b2f2bb), light yellow (#fff3bf), light purple (#d0bfff), light pink (#fef2f0), light teal (#c3fae8), light gray (#e9ecef).
- Input/output boxes: pastel orange (#ffd8a8).
- Orchestrator banner: light coral (#ffc9c9).
- All text: dark (#1e1e1e). No bright/saturated fills.

TITLE RULE: Slide title = plain bold marker text at top-left. NO box around the title.

TEXT CLARITY — HIGHEST PRIORITY: Every character crisp and readable at 30pt+. Generous spacing. NEVER overlap text. Module names in smaller text below each stage box.

LAYOUT LAW: STRICT left-to-right horizontal flow. Seven stage boxes in a single row connected by right-arrows. Input on far left, output on far right. Orchestrator banner below spanning full width. ALL arrows point RIGHT only.

FORBIDDEN — ZERO TOLERANCE:
- NO hub-and-spoke, radial, circular, or fan-out arrangements
- NO diagonal arrows, NO upward arrows
- NO step numbers, NO digits indicating sequence
- NO cluttered or overlapping elements"""


if __name__ == "__main__":
    main()
