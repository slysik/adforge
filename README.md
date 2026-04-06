# AdForge

AdForge is a proof-of-concept creative automation app for localized social campaigns, built for the Adobe Forward Deployed Engineer - Creative Technologist assessment interview.

It is intentionally framed as more than an image-generation demo. The goal is to show how a hands-on creative technologist would structure a client-facing prototype that is easy to explain, maintain, extend, and defend in a live review.

The project intent is documented in [ADFORGE_INTENT.md](./ADFORGE_INTENT.md).

## Why This Exists

The assessment is evaluating more than whether the code runs. AdForge is designed to demonstrate:

- rapid prototyping with clear technical judgment
- practical GenAI orchestration inside a real creative workflow
- strong system boundaries across inputs, generation, composition, validation, and reporting
- an implementation that maps cleanly to business goals and creative-operations pain points
- an artifact that can be presented credibly to both engineering and client stakeholders

## What It Does

Given a **campaign brief** (YAML/JSON), this pipeline:

1. **Parses** campaign details — products, target audience, brand guidelines, aspect ratios, languages
2. **Discovers or generates** hero images — reuses existing assets or generates new ones via DALL-E 3
3. **Composites** final ad creatives — resizing, text overlays, logo placement, brand styling
4. **Validates** output — brand compliance checks and legal content screening
5. **Reports** results — console summary, JSON data, and visual HTML report

![Pipeline Flow](https://img.shields.io/badge/Input-Campaign_Brief-blue) → ![GenAI](https://img.shields.io/badge/GenAI-DALL--E_3-green) → ![Composition](https://img.shields.io/badge/Composition-Pillow-orange) → ![Validation](https://img.shields.io/badge/Validation-Brand_%26_Legal-red) → ![Output](https://img.shields.io/badge/Output-Organized_Assets-purple)

---

> **AdForge** turns a campaign brief into reviewable social ad variants through a clear pipeline: resolve assets, generate missing heroes, compose placements, validate outputs, and report the result.

---

## Quick Start

### Prerequisites

- Python 3.9+
- (Optional) OpenAI API key for real image generation

### Setup

```bash
# Clone the repo
git clone https://github.com/slysik/adforge.git
cd adforge

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Generate sample input assets (logo + test product image)
python create_sample_assets.py

# (Optional) Set your OpenAI API key for real image generation
cp .env.example .env
# Edit .env with your key
```

### Run the Pipeline

```bash
# Mock mode (no API key needed — generates placeholder images)
python -m src.cli generate sample_briefs/summer_campaign.yaml --mock

# With real GenAI (requires OPENAI_API_KEY)
python -m src.cli generate sample_briefs/summer_campaign.yaml

# Custom input/output directories
python -m src.cli generate brief.yaml -i ./my_assets -o ./my_output

# Validate a brief without generating
python -m src.cli validate sample_briefs/summer_campaign.yaml

# Run the holiday beauty campaign (3 languages, 18 creatives)
python -m src.cli generate sample_briefs/holiday_campaign.yaml --mock
```

### Run Tests

```bash
pip install pytest
python -m pytest tests/ -v
```

---

## Example Input

### Campaign Brief (`sample_briefs/summer_campaign.yaml`)

```yaml
campaign:
  name: "Summer Refresh 2025"
  brand: "FreshCo"
  message: "Stay Fresh This Summer"
  tagline: "Naturally Refreshing"
  target_region: "North America"
  target_audience: "Health-conscious millennials and Gen Z, ages 22-38"

  languages:
    - en
    - es

  brand_guidelines:
    primary_colors: ["#00A86B", "#FFFFFF", "#1B1B1B"]
    logo_path: "input_assets/logo.png"
    prohibited_words: ["cheap", "discount", "knockoff", "diet"]

  products:
    - id: "sparkling-water"
      name: "FreshCo Sparkling Water"
      description: "Premium sparkling water with natural citrus essence"
      hero_image: null  # Will be generated
      keywords: [sparkling water, citrus, refreshing, summer drink]

    - id: "green-smoothie"
      name: "FreshCo Green Smoothie"
      description: "Organic green smoothie blend with kale and ginger"
      hero_image: "input_assets/green_smoothie.jpg"  # Pre-existing
      keywords: [green smoothie, organic, healthy, kale]

  aspect_ratios:
    - name: "instagram_square"
      ratio: "1:1"
      width: 1080
      height: 1080
    - name: "stories_reels"
      ratio: "9:16"
      width: 1080
      height: 1920
    - name: "facebook_landscape"
      ratio: "16:9"
      width: 1920
      height: 1080
```

### Example Output Structure

```
output/
└── summer_refresh_2025/
    ├── report.json              # Machine-readable results
    ├── report.html              # Visual HTML report
    ├── sparkling-water/
    │   ├── instagram_square/
    │   │   ├── hero.png          # Generated hero (1:1)
    │   │   ├── creative_en.jpg   # Final creative, English
    │   │   └── creative_es.jpg   # Final creative, Spanish
    │   ├── stories_reels/
    │   │   ├── hero.png          # Generated hero (9:16)
    │   │   ├── creative_en.jpg
    │   │   └── creative_es.jpg
    │   └── facebook_landscape/
    │       ├── hero.png          # Generated hero (16:9)
    │       ├── creative_en.jpg
    │       └── creative_es.jpg
    └── green-smoothie/
        ├── hero_base.png         # Copied from input (reused)
        ├── instagram_square/
        │   ├── creative_en.jpg
        │   └── creative_es.jpg
        ├── stories_reels/
        │   ├── creative_en.jpg
        │   └── creative_es.jpg
        └── facebook_landscape/
            ├── creative_en.jpg
            └── creative_es.jpg
```

**This brief generates 12 creatives** (2 products × 3 ratios × 2 languages) in ~3 seconds (mock) or ~60 seconds (with DALL-E 3).

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLI (cli.py)                             │
│                  click-based command interface                   │
└─────────────────────────┬───────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────────┐
│                   Pipeline (pipeline.py)                        │
│              Orchestrates the full workflow                      │
└──┬──────────┬───────────┬───────────┬────────────┬──────────────┘
   │          │           │           │            │
   ▼          ▼           ▼           ▼            ▼
┌──────┐  ┌────────┐  ┌──────────┐  ┌─────────┐  ┌────────┐
│Models│  │Storage │  │Generator │  │Compositor│  │Validator│
│      │  │Manager │  │(GenAI)   │  │(Pillow)  │  │(Brand/ │
│Pydantic│ │Local FS│  │DALL-E 3  │  │Resize   │  │ Legal) │
│schemas│  │I/O     │  │or Mock   │  │Overlay  │  │        │
└──────┘  └────────┘  └──────────┘  │Text     │  └────────┘
                                     │Logo     │
                                     └─────────┘
                                          │
                                     ┌────▼────┐
                                     │ Report  │
                                     │Console  │
                                     │JSON/HTML│
                                     └─────────┘
```

### Module Responsibilities

| Module | File | Role |
|--------|------|------|
| **Models** | `src/models.py` | Pydantic data models with validation |
| **CLI** | `src/cli.py` | Click-based command-line interface |
| **Pipeline** | `src/pipeline.py` | Orchestration: load brief → generate → compose → validate → report |
| **Generator** | `src/generator.py` | GenAI image generation (DALL-E 3 + mock mode) |
| **Compositor** | `src/compositor.py` | Image composition: resize, crop, text overlay, gradient, logo |
| **Validator** | `src/validator.py` | Brand compliance + legal content checks |
| **Storage** | `src/storage.py` | File-based asset management with organized output structure |
| **Report** | `src/report.py` | Console summary (Rich), JSON, and HTML visual report |

---

## Key Design Decisions

### 1. **YAML Campaign Briefs with Pydantic Validation**
Campaign briefs use YAML for human readability with Pydantic models for strict validation. This keeps the business contract explicit and ensures invalid briefs fail fast with clear errors instead of producing misleading outputs downstream.

### 2. **Hero Image Reuse Strategy**
The pipeline first checks for existing hero images (explicit path or auto-discovery in `input_assets/`) before falling back to GenAI generation. This:
- Avoids unnecessary API costs
- Respects pre-approved creative assets
- Enables hybrid workflows (some AI-generated, some manually created)

### 3. **Per-Ratio Hero Generation**
When an existing hero is not available, the pipeline generates a separate hero image at each target aspect ratio rather than generating a single 1:1 hero and cropping it. This avoids visible artifacts from cross-ratio cropping (e.g., text or composition elements from one ratio bleeding into another). For reused assets (from DAM / input folder), center-crop is applied since the source image was presumably composed for flexibility.

### 4. **Mock Mode for Development/Testing**
The mock mode generates deterministic placeholder images with distinct colors per product. This enables:
- Full pipeline testing without API keys
- Fast CI/CD runs
- Predictable output for debugging

### 5. **Composition Over Text-in-Image Generation**
Campaign text is composited via Pillow rather than baked into GenAI prompts. This gives:
- Precise typographic control (font, size, positioning)
- Exact message fidelity (no hallucinated text)
- Language switching without regenerating images
- Brand font consistency

### 6. **Modular Architecture**
Each concern (generation, composition, validation, storage, reporting) is isolated in its own module with clean interfaces. This makes it easy to:
- Swap DALL-E for another provider (Stability AI, Firefly, Midjourney)
- Replace local storage with S3/Azure Blob/Dropbox
- Add new validation rules
- Extend reporting

### 7. **Assessment-Oriented Scope**
AdForge is deliberately scoped as a defendable proof of concept for an interview setting. It focuses on a coherent end-to-end workflow rather than trying to simulate a full production marketing platform.

---

## Features Checklist

### Required ✅
- [x] Accept campaign brief (YAML format)
- [x] Multiple products (2+ per brief)
- [x] Target region/market
- [x] Target audience
- [x] Campaign message
- [x] Accept/reuse existing input assets
- [x] Generate missing assets via GenAI (DALL-E 3)
- [x] Three aspect ratios (1:1, 9:16, 16:9)
- [x] Campaign message displayed on final creatives
- [x] Runs locally (CLI tool)
- [x] Output organized by product and aspect ratio
- [x] Documentation (this README)

### Nice-to-Have ✅
- [x] Brand compliance checks (color presence, logo, prohibited words)
- [x] Legal content checks (flagging regulated advertising terms)
- [x] Logging/reporting (console summary, JSON report, HTML visual report)
- [x] Multi-language support with explicit translation provider (EN, ES, FR, DE, PT, JA, ZH)
- [x] Mock mode for testing without API keys (clean, label-free procedural images)
- [x] Evidence-backed compliance results (passed/warning/failed/not_checked with notes)
- [x] Test suite (83 tests covering models, composition, generation, validation, pipeline)

---

## Assumptions & Limitations

### Assumptions
- **Per-ratio generation** is preferred for generated heroes; reused assets use center-crop
- **Translation** uses an explicit provider with pre-approved translations; unknown text falls back to source language with a warning (never silent). A production system would integrate DeepL / Google Translate with human review
- **Brand compliance** uses pixel sampling for colors and pixel-level region checks for logo presence; production would use CV-based template matching
- **Font availability** depends on the OS; the compositor tries family-specific paths, then generic fallbacks

### Limitations
- **DALL-E 3 size constraints**: Only supports 1024×1024, 1024×1792, 1792×1024 — final dimensions are achieved via resize/crop
- **No content-aware cropping**: Reused heroes use center-crop; a production system would use saliency detection
- **Curated translation table**: Only supports pre-approved translations; unknown text returns source language with a warning
- **No approval workflow**: This is a generation pipeline; a production system needs review/approval stages
- **No A/B variant generation**: Generates one variant per product/ratio/language; production should support multiple creative variants
- **No performance analytics integration**: Reports on generation but not on downstream ad performance
- **Single-threaded generation**: API calls are sequential; production should parallelize with async/await

### What I'd Improve Next
1. **Async pipeline** with `asyncio` for parallel image generation
2. **Content-aware cropping** using saliency detection (OpenCV) or Firefly's generative fill
3. **Dynamic translation** via DeepL or Google Translate API
4. **Template system** for different ad layouts (product-focused, lifestyle, promotional)
5. **Cloud storage integration** (S3/Azure Blob) with CDN delivery
6. **Approval workflow** with Slack/email notifications
7. **A/B variant generation** with multiple creative options per placement
8. **Performance tracking** integration with ad platform APIs
9. **Cost tracking** per generation (API costs, time)
10. **Caching layer** to avoid regenerating identical prompts

---

## Project Structure

```
adforge/
├── README.md                    # This file
├── ADFORGE_INTENT.md            # Product and interview intent
├── requirements.txt             # Python dependencies
├── .env.example                 # Environment variable template
├── .gitignore
├── create_sample_assets.py      # Script to generate test assets
├── sample_briefs/
│   ├── summer_campaign.yaml     # Example: consumer goods campaign
│   └── holiday_campaign.yaml    # Example: luxury beauty campaign
├── input_assets/
│   ├── logo.png                 # Generated brand logo
│   └── green_smoothie.jpg       # Sample pre-existing product asset
├── src/
│   ├── __init__.py
│   ├── __main__.py              # python -m src entry point
│   ├── cli.py                   # Click CLI commands
│   ├── pipeline.py              # Main orchestrator
│   ├── models.py                # Pydantic data models
│   ├── generator.py             # GenAI image generation
│   ├── compositor.py            # Image composition & text overlay
│   ├── validator.py             # Brand & legal compliance
│   ├── storage.py               # Asset storage manager
│   └── report.py                # Console, JSON, HTML reporting
├── tests/
│   ├── test_models.py           # Schema enforcement, validation
│   ├── test_generator.py        # Mock image generation contracts
│   ├── test_compositor.py       # Layout, text rendering, branding
│   ├── test_validator.py        # Compliance + legal checks
│   ├── test_storage.py          # File management
│   └── test_pipeline.py         # End-to-end integration
└── output/                      # Generated creatives (gitignored)
```

---

## CLI Reference

```bash
# Generate creatives from a campaign brief
python -m src.cli generate <BRIEF_FILE> [OPTIONS]  # aka "adforge generate"

Options:
  -i, --input-dir   Input assets directory (default: input_assets)
  -o, --output-dir  Output directory (default: output)
  --mock            Use mock image generation (no API key needed)
  --api-key         OpenAI API key (or set OPENAI_API_KEY env var)
  -v, --verbose     Enable debug logging

# Validate a brief file
python -m src.cli validate <BRIEF_FILE>

# Show version
python -m src.cli --version
```

---

## About the Name

**AdForge** is meant to communicate transformation with discipline: structured campaign inputs go in, reviewable creative outputs come out. The name fits the interview goal better than a generic "pipeline" label because it suggests both craft and repeatable production.

## License

MIT
