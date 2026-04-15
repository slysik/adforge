#!/usr/bin/env python3
"""
Batch slide generator for AdForge module architecture diagrams.

Uses the same Gemini image generation + vision evaluation as autoresearch.py,
but generates one slide per module (no optimization loop — single-shot).

Usage:
    python3 generate_slides.py                # Generate all slides
    python3 generate_slides.py --only app     # Generate only app slide
    python3 generate_slides.py --only models,providers  # Specific modules
    python3 generate_slides.py --eval-only    # Re-evaluate existing slides
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ─── Config ───────────────────────────────────────────────────────────────────

GEMINI_KEY = os.getenv("NANO_BANANA_API_KEY") or os.getenv("GEMINI_API_KEY")
GEN_MODEL = "gemini-3.1-flash-image-preview"
EVAL_MODEL = "gemini-2.5-flash"
OUTPUT_DIR = Path(__file__).resolve().parent / "docs" / "slides"

STYLE_RULES = (
    "Rich hand-drawn sketchnote illustration style: bold marker fonts, "
    "hand-drawn pictogram icons, dashed rough-edged borders, soft pastel watercolor fills. "
    "16:9 landscape orientation. Fill the FULL WIDTH of a wide horizontal canvas. "
    "Clean, professional, suitable for an engineering interview presentation. "
    "All text must be clearly readable at presentation distance (30pt+ equivalent). "
    "Do NOT include any photos or realistic imagery — diagram/illustration only."
)

# ─── Slide Definitions ───────────────────────────────────────────────────────

SLIDES = {
    "app_execution_flow": {
        "title": "AdForge: Application Execution Flow",
        "filename": "app-execution-flow.png",
        "description": (
            "Overview slide showing HOW a user interacts with AdForge — the two entry points "
            "and what happens when they run the pipeline.\n\n"
            "TITLE: 'AdForge: Application Execution Flow' — bold marker text at top.\n\n"
            "LAYOUT: Two swim lanes side by side, merging into a shared pipeline.\n\n"
            "LEFT LANE — 'CLI Path' (light blue fill):\n"
            "  Box 1: 'User writes campaign.yaml' with a code editor icon\n"
            "  Box 2: 'adforge generate campaign.yaml' with terminal icon\n"
            "  Box 3: 'cli.py parses args via Click' with gear icon\n\n"
            "RIGHT LANE — 'Streamlit UI Path' (light green fill):\n"
            "  Box 1: 'User fills Brief Builder form' with a form/pencil icon\n"
            "  Box 2: 'Clicks Run Pipeline button' with play button icon\n"
            "  Box 3: 'app.py validates & launches' with rocket icon\n\n"
            "MERGE POINT: Both lanes feed into a single box:\n"
            "  'pipeline.py — run_pipeline()' with a funnel/merge icon (light coral fill)\n"
            "  Below it: '7 Stages | ThreadPoolExecutor | Per-stage metrics'\n\n"
            "BOTTOM — Three output boxes side by side (light yellow fill):\n"
            "  'Console Report' with terminal icon\n"
            "  'HTML Dashboard' with browser icon\n"
            "  '18 Creative PNGs' with image grid icon\n\n"
            "Arrows flow TOP to BOTTOM. Clean vertical flow, not horizontal.\n"
            "Each box has rounded dashed borders and pastel fill colors."
        ),
    },
    "models": {
        "title": "models.py — Data Validation Boundary",
        "filename": "models.png",
        "description": (
            "Architecture slide showing how models.py acts as the data validation boundary.\n\n"
            "TITLE: 'models.py — Data Validation Boundary' at top.\n\n"
            "LAYOUT: Center column with validation flow, flanked by examples.\n\n"
            "TOP: 'Campaign Brief (YAML)' input box with document icon (pastel orange)\n\n"
            "CENTER — Four Pydantic model boxes stacked vertically (light blue fills):\n"
            "  'CampaignBrief' — 'Top-level container: brand + products + settings'\n"
            "  'BrandGuidelines' — 'Hex color regex, logo path, tagline'\n"
            "  'Product' — 'Name, description, keywords, visual theme'\n"
            "  'PipelineResult' — 'Output container: assets + metrics + warnings'\n\n"
            "LEFT SIDE — 'What Gets Validated' callout boxes (light red/pink fills):\n"
            "  'Hex colors match ^#[0-9a-fA-F]{6}$'\n"
            "  'Languages are ISO 639-1 codes'\n"
            "  'Min 2 products required'\n"
            "  'Min 3 aspect ratios required'\n\n"
            "RIGHT SIDE — 'What Gets Rejected' with X icons:\n"
            "  'Invalid hex: #GGHHII'\n"
            "  'Unknown language: xx'\n"
            "  'Only 1 product'\n\n"
            "BOTTOM: Arrow to 'Clean, validated data → Pipeline Stage 1' (light green)\n\n"
            "Arrows flow top to bottom through the validation stack."
        ),
    },
    "providers": {
        "title": "providers.py — Image Generation Abstraction",
        "filename": "providers.png",
        "description": (
            "Architecture slide showing the provider abstraction layer.\n\n"
            "TITLE: 'providers.py — Image Generation Abstraction' at top.\n\n"
            "LAYOUT: Factory pattern with auto-detect chain plus explicit-selection callout.\n\n"
            "TOP: 'pipeline.py calls get_provider()' box (light coral)\n\n"
            "CENTER — 'Auto-Detect Chain' as a horizontal provider flow (left to right):\n"
            "  'FireflyProvider' box (light red) labeled 'Future option — requires FIREFLY_CLIENT_ID + FIREFLY_CLIENT_SECRET'\n"
            "  'GeminiProvider' box (light blue) labeled 'Current runtime path when GEMINI_API_KEY is present'\n"
            "  'MockProvider' box (light gray) labeled 'Always-available fallback'\n\n"
            "MID-PAGE CALLOUT — Explicit selection path:\n"
            "  'provider_type=firefly|gemini|dalle → selected provider or RuntimeError if unavailable'\n"
            "  'mock=True or provider_type=mock → MockProvider'\n\n"
            "BELOW EACH PROVIDER — Key details:\n"
            "  Firefly: 'Model: firefly-v3 | expand() available for future use'\n"
            "  Gemini: 'google-genai SDK | imagen-4.0-generate-001'\n"
            "  DALL-E: 'Explicit only | model: dall-e-3'\n"
            "  Mock: 'Deterministic procedural images | Brand colors from prompt'\n\n"
            "LEFT SIDE — 'ImageProvider ABC' interface box (light yellow):\n"
            "  'generate(prompt, width, height, output_path, style_reference=None) → (PIL.Image, GenerationMetadata)'\n"
            "  'is_available() → bool'\n"
            "  'provider_type → ProviderType'\n"
            "  'model_name → str'\n\n"
            "RIGHT SIDE — 'Retry Logic' box (light green):\n"
            "  '_retry_api_call() — exponential backoff + jitter'\n"
            "  '_is_transient_error() — 429, 5xx, ConnectionError'\n"
            "  'Max 3 retries, 30s max delay'\n\n"
            "BOTTOM: 'Providers save hero image to output_path, return GenerationMetadata, and pipeline.py passes hero file path to compositor.py' (light purple)"
        ),
    },
    "analyzer": {
        "title": "analyzer.py — Brief Quality Scoring",
        "filename": "analyzer.png",
        "description": (
            "Architecture slide showing the dual-path brief analysis system.\n\n"
            "TITLE: 'analyzer.py — Brief Quality Scoring' at top.\n\n"
            "LAYOUT: Two parallel paths merging into a single output.\n\n"
            "TOP: 'CampaignBrief' input box (pastel orange)\n\n"
            "TWO PATHS side by side:\n\n"
            "LEFT — 'HeuristicAnalyzer' (light blue fill):\n"
            "  'Keyword density check'\n"
            "  'Description length scoring'\n"
            "  'Color palette completeness'\n"
            "  'Always available — $0 cost'\n\n"
            "RIGHT — 'LLMAnalyzer' (light purple fill):\n"
            "  'GPT-4o-mini evaluation'\n"
            "  'Strategic quality assessment'\n"
            "  'Creative direction suggestions'\n"
            "  'Optional — requires API key'\n\n"
            "MERGE: Both feed into 'BriefAnalysis' result box (light green):\n"
            "  'quality_score: 0-100'\n"
            "  'suggestions: list[str]'\n"
            "  'enrichment: creative direction text'\n\n"
            "BOTTOM: 'Score gates pipeline — low score = warning before burning GPU budget'\n\n"
            "Key insight callout: 'AI as judgment, not generation — scores before spending'"
        ),
    },
    "compositor": {
        "title": "compositor.py — Deterministic Text Composition",
        "filename": "compositor.png",
        "description": (
            "Architecture slide showing how compositor.py layers text onto hero images.\n\n"
            "TITLE: 'compositor.py — Deterministic Text Composition' at top.\n\n"
            "LAYOUT: Layered stack showing composition pipeline.\n\n"
            "TOP: Two inputs side by side:\n"
            "  'Hero Image (from providers.py)' (light purple) and 'Template (from templates.py)' (light yellow)\n\n"
            "CENTER — Composition Stack (5 layers, bottom to top, like Photoshop layers):\n"
            "  Layer 1 (bottom): 'Hero Image — resized to target ratio' (light blue)\n"
            "  Layer 2: 'Gradient Overlay — brand color to transparent' (light coral)\n"
            "  Layer 3: 'Headline Text — Pillow text with shadow' (light green)\n"
            "  Layer 4: 'Body Copy — auto-wrapped, multi-language' (light green)\n"
            "  Layer 5 (top): 'Logo — 12% of shorter dimension, top-right' (light yellow)\n\n"
            "RIGHT SIDE — 'Why Pillow, Not AI?' callout (light red):\n"
            "  'Zero hallucinated text'\n"
            "  'Exact font control'\n"
            "  'Instant language switching'\n"
            "  'Deterministic output'\n\n"
            "LEFT SIDE — 'Translation' callout (light teal):\n"
            "  'Curated lookup table'\n"
            "  'NOT machine translation'\n"
            "  'Human-reviewed ad copy'\n\n"
            "BOTTOM: '9 heroes × 2 languages = 18 composited assets'"
        ),
    },
    "templates": {
        "title": "templates.py — Layout Strategy System",
        "filename": "templates.png",
        "description": (
            "Architecture slide showing the 5 template strategies and auto-selection.\n\n"
            "TITLE: 'templates.py — Layout Strategy System' at top.\n\n"
            "LAYOUT: Decision tree on left, 5 template thumbnails on right.\n\n"
            "LEFT — 'auto_select_template()' decision flow (top to bottom):\n"
            "  Diamond: 'Luxury brand?' → Yes: 'MINIMAL'\n"
            "  Diamond: 'Short headline?' → Yes: 'BOLD_TYPE'\n"
            "  Diamond: '9:16 portrait?' → Yes: 'SPLIT_PANEL'\n"
            "  Diamond: 'Long description?' → Yes: 'EDITORIAL'\n"
            "  Default: 'PRODUCT_HERO'\n\n"
            "RIGHT — Five template preview boxes in a grid (2x3, last row centered):\n"
            "  'PRODUCT_HERO' — 'Hero fills frame, text overlay at bottom' (light blue)\n"
            "  'EDITORIAL' — 'Magazine-style with large text area' (light green)\n"
            "  'SPLIT_PANEL' — 'Image left, text right (or top/bottom)' (light yellow)\n"
            "  'MINIMAL' — 'Clean, lots of whitespace, luxury feel' (light purple)\n"
            "  'BOLD_TYPE' — 'Typography-forward, large headline' (light coral)\n\n"
            "BOTTOM: 'Strategy Pattern — $0, 0ms, fully auditable vs LLM selection'\n\n"
            "Key callout: 'Heuristic rules encode creative director judgment'"
        ),
    },
    "validator": {
        "title": "validator.py — Brand Compliance Engine",
        "filename": "validator.png",
        "description": (
            "Architecture slide showing the three compliance check categories.\n\n"
            "TITLE: 'validator.py — Brand Compliance Engine' at top.\n\n"
            "LAYOUT: Three parallel check lanes feeding into a compliance report.\n\n"
            "TOP: 'Composited Creative (PNG)' input box (light purple)\n\n"
            "THREE CHECK LANES side by side:\n\n"
            "LANE 1 — 'Pixel-Level Checks' (light blue):\n"
            "  'Sample every 10th pixel'\n"
            "  'Brand color presence ≥ threshold'\n"
            "  'Dominant color analysis'\n"
            "  Icon: magnifying glass over pixels\n\n"
            "LANE 2 — 'Logo Checks' (light yellow):\n"
            "  'Logo region detection'\n"
            "  'Placement verification'\n"
            "  'Size proportion check'\n"
            "  Icon: shield with checkmark\n\n"
            "LANE 3 — 'Text Checks' (light coral):\n"
            "  'Prohibited word scan'\n"
            "  'Legal disclaimer presence'\n"
            "  'Competitor mention detection'\n"
            "  Icon: document with warning\n\n"
            "BOTTOM — 'ComplianceResult' output (light green):\n"
            "  'passed: bool | warnings: list | violations: list'\n\n"
            "Key callout: 'No AI vision model — deterministic, verifiable, no false negatives'"
        ),
    },
    "storage": {
        "title": "storage.py — Asset Storage & Caching",
        "filename": "storage.png",
        "description": (
            "Architecture slide showing storage.py's caching and file management.\n\n"
            "TITLE: 'storage.py — Asset Storage & Caching' at top.\n\n"
            "LAYOUT: Input/output flow with cache decision diamond.\n\n"
            "TOP: 'Pipeline requests hero image' input (light coral)\n\n"
            "CENTER — Cache Decision:\n"
            "  Diamond: 'Hero in cache?' (light yellow)\n"
            "  Yes path (right): 'Return cached hero — $0 API cost' with speed icon (light green)\n"
            "  No path (down): 'Generate via provider → Save to cache' (light blue)\n\n"
            "BELOW — File System Layout box (light gray):\n"
            "  'output/'\n"
            "  '  campaign_slug/'\n"
            "  '    heroes/         — cached hero images'\n"
            "  '    composited/     — final creatives'\n"
            "  '    report.html     — dashboard'\n"
            "  '    report.json     — machine-readable'\n\n"
            "RIGHT SIDE — 'Key Functions' (light purple):\n"
            "  'discover_hero() — find existing hero by product+ratio'\n"
            "  'save_hero() — persist with metadata'\n"
            "  'export_zip() — bundle for delivery'\n\n"
            "BOTTOM: 'Hero reuse across runs reduces API costs to zero for cached assets'"
        ),
    },
    "tracker": {
        "title": "tracker.py — Pipeline Metrics & Cost Tracking",
        "filename": "tracker.png",
        "description": (
            "Architecture slide showing how tracker.py instruments the pipeline.\n\n"
            "TITLE: 'tracker.py — Pipeline Metrics & Cost Tracking' at top.\n\n"
            "LAYOUT: Pipeline stages with timing bars and metrics output.\n\n"
            "TOP: 'PipelineTracker wraps each stage' (light coral)\n\n"
            "CENTER — 7 stages as a horizontal timeline bar chart:\n"
            "  Each stage is a colored bar with duration shown:\n"
            "  'Ingest (0.1s)' | 'Analyze (1.2s)' | 'Cache (0.3s)' | 'Generate (15s)' | 'Compose (3s)' | 'Validate (0.5s)' | 'Report (0.2s)'\n"
            "  'Generate' bar is the longest (dominates runtime)\n\n"
            "BELOW — Two metric cards side by side:\n"
            "  'StageMetrics' (light blue): 'stage_name, duration_ms, api_calls, errors'\n"
            "  'AssetMetrics' (light green): 'asset_id, provider, generation_time, cost_estimate'\n\n"
            "RIGHT — 'Context Manager Pattern' callout (light yellow):\n"
            "  'with tracker.stage(\"generate\"):'\n"
            "  '    # automatic timing'\n"
            "  '    # automatic error counting'\n\n"
            "BOTTOM: 'Per-stage timing reveals bottlenecks — generation is 70%+ of total runtime'"
        ),
    },
    "report": {
        "title": "report.py — Multi-Format Reporting",
        "filename": "report.png",
        "description": (
            "Architecture slide showing report.py's three output formats.\n\n"
            "TITLE: 'report.py — Multi-Format Reporting' at top.\n\n"
            "LAYOUT: Single input splitting into three output channels.\n\n"
            "TOP: 'PipelineResult' input box (light coral)\n"
            "  'assets + metrics + warnings + compliance results'\n\n"
            "THREE OUTPUT CHANNELS fanning out below:\n\n"
            "CHANNEL 1 — 'Console Summary' (light blue):\n"
            "  Terminal window mockup showing:\n"
            "  '✓ 18 assets generated'\n"
            "  '✓ 16 passed compliance'\n"
            "  '⚠ 2 warnings'\n"
            "  'Best for: developers, CI/CD logs'\n\n"
            "CHANNEL 2 — 'JSON Report' (light green):\n"
            "  Code block showing:\n"
            "  '{\"assets\": [...], \"metrics\": {...}}'\n"
            "  'Best for: downstream tools, APIs'\n\n"
            "CHANNEL 3 — 'HTML Dashboard' (light purple):\n"
            "  Browser window mockup showing:\n"
            "  'Asset grid + compliance badges'\n"
            "  'Best for: stakeholders, reviews'\n\n"
            "BOTTOM: 'Same data, three audiences — developer, machine, stakeholder'"
        ),
    },
    "analytics": {
        "title": "analytics.py — KPI Simulation & Winner Detection",
        "filename": "analytics.png",
        "description": (
            "Architecture slide showing analytics.py's simulated performance metrics.\n\n"
            "TITLE: 'analytics.py — KPI Simulation & Winner Detection' at top.\n\n"
            "LAYOUT: Input → simulation → ranking output.\n\n"
            "TOP: '18 Composited Creatives' input box (light purple)\n\n"
            "CENTER — 'KPI Simulation Engine' box (light blue):\n"
            "  Four metric boxes in a row:\n"
            "  'CTR' (click-through rate) with mouse cursor icon\n"
            "  'CPA' (cost per acquisition) with dollar icon\n"
            "  'Impressions' with eye icon\n"
            "  'Conversions' with target icon\n"
            "  Below: 'Deterministic seeded simulation — reproducible results'\n\n"
            "BELOW — 'Winner Detection' section (light green):\n"
            "  Podium visualization:\n"
            "  '🥇 Best CPA: product_A_16x9_en — $2.31'\n"
            "  '🥈 Runner-up: product_B_1x1_en — $2.87'\n"
            "  '🥉 Third: product_A_1x1_es — $3.12'\n\n"
            "RIGHT — 'CreativeKPI dataclass' (light yellow):\n"
            "  'creative_id, ctr, cpa, impressions, conversions'\n\n"
            "BOTTOM: 'Identifies winning creatives for budget reallocation'"
        ),
    },
    "cli": {
        "title": "cli.py — Command-Line Interface",
        "filename": "cli.png",
        "description": (
            "Architecture slide showing cli.py's Click-based command structure.\n\n"
            "TITLE: 'cli.py — Command-Line Interface' at top.\n\n"
            "LAYOUT: Command tree with usage examples.\n\n"
            "TOP: 'adforge' root command (light coral) with terminal icon\n\n"
            "FOUR SUBCOMMANDS branching down:\n\n"
            "  'adforge generate campaign.yaml' (light blue):\n"
            "    'Run full pipeline from YAML brief'\n"
            "    '--output-dir, --provider, --skip-cache'\n\n"
            "  'adforge validate campaign.yaml' (light green):\n"
            "    'Validate brief without running pipeline'\n"
            "    'Quick syntax and schema check'\n\n"
            "  'adforge analyze campaign.yaml' (light yellow):\n"
            "    'Score brief quality (heuristic + LLM)'\n"
            "    'Preview enrichment suggestions'\n\n"
            "  'adforge providers' (light purple):\n"
            "    'List available image providers'\n"
            "    'Show auto-detect chain result'\n\n"
            "BOTTOM — 'CI/CD Integration' box (light gray):\n"
            "  'adforge generate brief.yaml --provider mock --output-dir artifacts/'\n"
            "  'Exit code 0 = success, 1 = validation failure'\n\n"
            "Key callout: 'Click framework — --help on every command'"
        ),
    },
    "utils": {
        "title": "utils.py — Shared Utility Functions",
        "filename": "utils.png",
        "description": (
            "Architecture slide showing utils.py's shared helper functions.\n\n"
            "TITLE: 'utils.py — Shared Utility Functions' at top.\n\n"
            "LAYOUT: Three utility function cards with usage arrows showing which modules call them.\n\n"
            "THREE FUNCTION CARDS in a row:\n\n"
            "CARD 1 — 'hex_to_rgb()' (light blue):\n"
            "  'Input: \"#FF6B00\"'\n"
            "  'Output: (255, 107, 0)'\n"
            "  'Used by: compositor.py, validator.py'\n\n"
            "CARD 2 — 'relative_luminance()' (light green):\n"
            "  'Input: (255, 107, 0)'\n"
            "  'Output: 0.285'\n"
            "  'Used by: compositor.py (contrast checks)'\n\n"
            "CARD 3 — 'smart_resize()' (light purple):\n"
            "  'Input: image + target ratio'\n"
            "  'Output: resized image'\n"
            "  'Used by: compositor.py, storage.py'\n\n"
            "BELOW — Dependency graph showing arrows from calling modules to utils:\n"
            "  compositor.py → all three functions\n"
            "  validator.py → hex_to_rgb\n"
            "  storage.py → smart_resize\n\n"
            "BOTTOM: 'DRY primitives — simple, tested, no dependencies'"
        ),
    },
}

# ─── Evaluation Rubric ───────────────────────────────────────────────────────

EVAL_PROMPT = """You are evaluating a software architecture presentation slide for an engineering interview. Score STRICTLY against these 6 criteria.

SCORING: Each criterion is scored 0-4:
  4 = Excellent — fully meets the criterion with no issues
  3 = Good — meets criterion with minor issues
  2 = Fair — partially meets criterion, noticeable issues
  1 = Poor — mostly fails criterion
  0 = Fail — does not meet criterion at all

Criteria:

1. LEGIBILITY (0-4): ALL text is clearly readable — no garbled, overlapping, blurry, or cut-off text. All words are real English words spelled correctly. Font size is large enough to present.

2. CORRECTNESS (0-4): The technical content is accurate. Module names, function names, and descriptions match what the slide claims. No fabricated or incorrect technical details.

3. SOLUTION_ARCH_BEST_PRACTICES (0-4): Follows architecture diagramming conventions: clear inputs/outputs, labeled components, technology annotations present. Would be appropriate for a technical interview.

4. SIMPLICITY (0-4): An engineer could understand the slide in under 30 seconds. Not cluttered. Clear visual hierarchy. Concise labels.

5. VISUAL_DESIGN (0-4): Professional, polished, consistent colors. Clean alignment and spacing. Cohesive aesthetic suitable for an interview presentation.

6. LAYOUT (0-4): The diagram flows in a clear, logical direction. Components are well-organized spatially. No confusing overlaps or disconnected elements.

Respond in this exact JSON format ONLY — no markdown, no explanation:
{"legibility": 4, "correctness": 4, "solution_arch": 4, "simplicity": 4, "visual_design": 4, "layout": 4, "total": 24, "failures": []}

Be strict. Deduct points for specific issues. Add brief descriptions to failures array for any criterion below 4."""

# ─── Generation & Evaluation ─────────────────────────────────────────────────


def generate_slide(gemini_client, slide_id: str, slide_def: dict, output_path: Path) -> bool:
    """Generate a single architecture slide via Gemini image generation."""
    from google.genai import types

    prompt = (
        f"{STYLE_RULES}\n\n"
        f"--- SLIDE TO CREATE ---\n"
        f"TITLE: {slide_def['title']}\n\n"
        f"CONTENT & LAYOUT:\n{slide_def['description']}"
    )

    try:
        response = gemini_client.models.generate_content(
            model=GEN_MODEL,
            contents=prompt,
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
        print(f"    No image in response for {slide_id}")
        return False
    except Exception as e:
        print(f"    GEN ERROR ({slide_id}): {e}")
        return False


def evaluate_slide(gemini_client, image_path: Path) -> dict | None:
    """Evaluate slide against rubric via Gemini vision."""
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
        result["total"] = sum(
            result.get(k, 0)
            for k in ["legibility", "correctness", "solution_arch", "simplicity", "visual_design", "layout"]
        )
        return result
    except Exception as e:
        print(f"    EVAL ERROR: {e}")
        return None


# ─── Main ─────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Generate AdForge module architecture slides")
    parser.add_argument("--only", help="Comma-separated list of slide IDs to generate")
    parser.add_argument("--eval-only", action="store_true", help="Re-evaluate existing slides")
    parser.add_argument("--no-eval", action="store_true", help="Skip evaluation step")
    args = parser.parse_args()

    if not GEMINI_KEY:
        print("ERROR: Set GEMINI_API_KEY or NANO_BANANA_API_KEY")
        sys.exit(1)

    from google import genai
    client = genai.Client(api_key=GEMINI_KEY)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Determine which slides to generate
    if args.only:
        slide_ids = [s.strip() for s in args.only.split(",")]
        slides = {k: v for k, v in SLIDES.items() if k in slide_ids}
        if not slides:
            print(f"ERROR: No matching slides. Available: {', '.join(SLIDES.keys())}")
            sys.exit(1)
    else:
        slides = SLIDES

    results = {}
    total = len(slides)

    for i, (slide_id, slide_def) in enumerate(slides.items(), 1):
        output_path = OUTPUT_DIR / slide_def["filename"]
        print(f"\n{'='*60}")
        print(f"[{i}/{total}] {slide_def['title']}")
        print(f"{'='*60}")

        if not args.eval_only:
            print(f"  Generating...")
            ok = generate_slide(client, slide_id, slide_def, output_path)
            if not ok:
                print(f"  FAILED — skipping")
                results[slide_id] = {"status": "failed"}
                continue
            print(f"  Saved: {output_path}")

            # Rate limit — Gemini has per-minute limits
            if i < total:
                print(f"  Waiting 5s for rate limit...")
                time.sleep(5)

        if not args.no_eval:
            if not output_path.exists():
                print(f"  No image to evaluate — skipping")
                results[slide_id] = {"status": "no_image"}
                continue

            print(f"  Evaluating...")
            eval_result = evaluate_slide(client, output_path)
            if eval_result:
                score = eval_result["total"]
                print(f"  SCORE: {score}/24")
                print(f"    Legibility:    {eval_result.get('legibility', 0)}/4")
                print(f"    Correctness:   {eval_result.get('correctness', 0)}/4")
                print(f"    Solution Arch: {eval_result.get('solution_arch', 0)}/4")
                print(f"    Simplicity:    {eval_result.get('simplicity', 0)}/4")
                print(f"    Visual Design: {eval_result.get('visual_design', 0)}/4")
                print(f"    Layout:        {eval_result.get('layout', 0)}/4")
                if eval_result.get("failures"):
                    for f in eval_result["failures"]:
                        print(f"    ⚠ {f}")
                results[slide_id] = {"status": "ok", "score": score, "eval": eval_result}
            else:
                results[slide_id] = {"status": "eval_failed"}
        else:
            results[slide_id] = {"status": "ok", "score": "skipped"}

    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    for slide_id, result in results.items():
        status = result.get("status", "?")
        score = result.get("score", "—")
        title = SLIDES[slide_id]["title"]
        print(f"  {score:>6}/24  {title}")

    # Save results
    results_path = OUTPUT_DIR / "results.json"
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to {results_path}")
    print(f"Slides saved to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
