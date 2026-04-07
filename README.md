# AdForge

**Creative automation pipeline for localized social campaigns.**

Built for the Adobe Forward Deployed Engineer – Creative Technologist assessment. Designed to show how a hands-on creative technologist would structure a client-facing prototype: easy to explain, maintain, extend, and defend live.

Full intent documented in [ADFORGE_INTENT.md](./ADFORGE_INTENT.md).

---

## What It Does

Given a **campaign brief** (YAML/JSON), AdForge runs a 7-stage pipeline:

```
Brief → Analyze → Resolve → Generate → Compose → Validate → Report
```

1. **Ingests** a structured campaign brief (products, audience, brand guidelines, placements)
2. **Analyzes** brief quality with a scoring engine (completeness, clarity, brand strength, targeting)
3. **Resolves** existing assets first — reuses what's available, generates only what's missing
4. **Generates** hero images via a provider chain: Adobe Firefly → DALL-E 3 → Mock
5. **Composes** final creatives using auto-selected layout templates with brand styling
6. **Validates** outputs against brand compliance and legal content rules
7. **Reports** results as console summary, JSON, and an interactive HTML dashboard

**Key differentiators:**
- **Adobe Firefly-first** provider architecture with graceful fallback chain
- **LLM-powered brief analysis** — GenAI as a judgment tool, not just an image generator
- **Multi-template layout system** — 5 composition templates auto-selected by content
- **Parallel generation** — ThreadPool-based hero generation across ratios
- **Cost & performance tracking** — per-stage timing and estimated cost in every report

---

## Quick Start

```bash
# Clone and setup
git clone https://github.com/slysik/adforge.git && cd adforge
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
python create_sample_assets.py

# Option A: Web UI (recommended for demo)
streamlit run src/app.py

# Option B: CLI
python -m src.cli generate sample_briefs/summer_campaign.yaml --mock

# Analyze a brief without generating
python -m src.cli analyze sample_briefs/holiday_campaign.yaml

# List available providers
python -m src.cli providers

# Run with DALL-E 3
export OPENAI_API_KEY=sk-your-key
python -m src.cli generate sample_briefs/summer_campaign.yaml

# Force a specific template
python -m src.cli generate brief.yaml --mock --template minimal

# Run tests (139 tests)
python -m pytest tests/ -v
```

---

## Web UI

AdForge includes a **Streamlit web interface** for visual campaign management:

```bash
streamlit run src/app.py
```

The UI provides:
- **Campaign overview** — brief metadata, analysis scores, product details
- **Creative gallery** — side-by-side ratio comparison per product with compliance badges
- **Pipeline metrics** — stage timing, cost breakdown, provider info
- **Pre-generated samples** — browse `sample_output/` without needing an API key
- **Live pipeline execution** — run the full pipeline from the browser with mock, Gemini, or Firefly

Two modes:
1. **Run Pipeline** — select a sample brief or upload a custom one, choose provider, run
2. **View Pre-generated Samples** — browse previously generated outputs from `sample_output/`

---

## Provider Architecture

AdForge uses a **provider abstraction** that makes image generation provider-swappable via configuration:

```
┌─────────────────────────────────────────────────────┐
│              ImageProvider (ABC)                     │
│  generate() → (Image, Metadata)                     │
└─────────┬──────────┬──────────┬──────────┬─────────┘
          │          │          │          │
    ┌─────▼──┐  ┌────▼───┐  ┌──▼─────┐ ┌─▼─────┐
    │Firefly │  │Imagen  │  │DALL-E 3│ │ Mock  │
    │Services│  │4.0     │  │        │ │       │
    │        │  │        │  │$0.04/  │ │$0.00  │
    │Generate│  │Native  │  │image   │ │       │
    │Expand  │  │aspect  │  │        │ │Determ-│
    │Fill    │  │ratios  │  │3 fixed │ │inistic│
    │Style   │  │        │  │sizes   │ │       │
    └────────┘  └────────┘  └────────┘ └───────┘
```

**Auto-resolution:** Firefly → Gemini → Mock. The pipeline always runs.

### Adobe Firefly Services

The `FireflyProvider` implements the Firefly Services REST API:
- **Text-to-Image** (`/v3/images/generate`) — primary hero generation
- **Generative Expand** (`/v3/images/expand`) — aspect-ratio adaptation without crop artifacts
- **Style Reference** — brand-consistent generation from reference images
- **IMS Authentication** — client_credentials grant with automatic token refresh

Set `FIREFLY_CLIENT_ID` + `FIREFLY_CLIENT_SECRET` from [Adobe Developer Console](https://developer.adobe.com/console/).

> In production, Generative Expand replaces center-crop for adapting existing assets to different aspect ratios. It generates contextually consistent content at the edges instead of cutting the image.

---

## Brief Analysis

Before generating anything, AdForge scores the brief on 4 dimensions (0–25 each, 100 total):

| Dimension | What It Checks |
|-----------|---------------|
| **Completeness** | Products, keywords, descriptions, hero assets, languages |
| **Clarity** | Action-oriented messaging, audience specificity, region targeting |
| **Brand Strength** | Color palette, accent color, logo, prohibited words, disclaimer, font |
| **Targeting** | Language count, aspect ratio coverage, platform reach |

The analyzer also:
- Identifies strengths and weaknesses
- Suggests actionable improvements
- Flags potential brand/legal risks (e.g., "guaranteed" in ad copy)
- Generates prompt enrichment context per product (audience-informed, region-informed)
- Infers creative direction recommendations

```
╭──────── Brief Analysis ─────────╮
│ Brief Quality Score: 88/100 (A) │
│   [█████████████████░░░]        │
│   Completeness:   23/25         │
│   Clarity:        22/25         │
│   Brand Strength: 21/25         │
│   Targeting:      22/25         │
╰─────────────────────────────────╯
```

This demonstrates **GenAI as a judgment tool** — the LLM analyzes strategy, not just generates images.

---

## Layout Templates

5 composition templates, auto-selected based on content signals:

| Template | When Selected | Layout |
|----------|---------------|--------|
| `product_hero` | Default — universally safe | Full-bleed hero + gradient + bottom text |
| `editorial` | Long messages | 60/40 hero/text split with brand panel |
| `split_panel` | Vertical formats (9:16) | 50/50 image/text with accent bar |
| `minimal` | Luxury/premium keywords | Centered hero, generous whitespace |
| `bold_type` | Short punchy messages | Oversized typography on tinted hero |

Auto-selection logic:
```python
if luxury_keywords:    → MINIMAL
if short_message:      → BOLD_TYPE
if vertical_format:    → SPLIT_PANEL
if long_message:       → EDITORIAL
else:                  → PRODUCT_HERO
```

Override with `--template <name>` on the CLI.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         CLI / API Layer                                 │
│                      click + REST-ready                                 │
└───────────────────────┬─────────────────────────────────────────────────┘
                        │
┌───────────────────────▼─────────────────────────────────────────────────┐
│                      Pipeline Orchestrator                              │
│        Ingest → Analyze → Resolve → Generate → Compose → Validate →    │
│                                                          Report        │
└──┬──────┬──────┬──────┬──────┬──────┬──────┬───────────────────────────┘
   │      │      │      │      │      │      │
   ▼      ▼      ▼      ▼      ▼      ▼      ▼
┌─────┐┌──────┐┌──────┐┌──────┐┌─────┐┌─────┐┌──────┐
│Brief││Brief ││Provid││Templ-││Compo││Valid││Report│
│Model││Analy-││er    ││ates  ││sitor││ator ││      │
│s    ││zer   ││Layer ││      ││     ││     ││JSON  │
│     ││      ││      ││5     ││Text ││Brand││HTML  │
│Pydan││Score ││Fire- ││layout││Logo ││Legal││Metro │
│tic  ││Enrich││fly   ││auto- ││Grad ││Pixel││ics   │
│     ││Risks ││DALL-E││select││     ││     ││      │
└─────┘└──────┘│Mock  │└──────┘└─────┘└─────┘└──────┘
               └──────┘
```

### Module Inventory

| Module | File | Purpose |
|--------|------|---------|
| **Models** | `src/models.py` | Pydantic schemas with validation (min products, hex colors, language codes) |
| **Pipeline** | `src/pipeline.py` | 7-stage orchestrator with parallel generation |
| **Providers** | `src/providers.py` | Firefly / DALL-E / Mock provider abstraction |
| **Analyzer** | `src/analyzer.py` | Brief quality scoring + prompt enrichment |
| **Templates** | `src/templates.py` | 5 layout templates with auto-selection |
| **Compositor** | `src/compositor.py` | Image composition, text overlay, translation |
| **Validator** | `src/validator.py` | Brand compliance + legal content checks |
| **Storage** | `src/storage.py` | Asset storage with organized output structure |
| **Tracker** | `src/tracker.py` | Per-stage timing and cost tracking |
| **Report** | `src/report.py` | Console, JSON, and interactive HTML dashboard |
| **CLI** | `src/cli.py` | Click commands: generate, validate, analyze, providers |

---

## Sample Output

### Summer Campaign (2 products × 3 ratios × 2 languages = 12 creatives)

```
output/summer_refresh_2025/
├── report.json              # Machine-readable results + metrics + analysis
├── report.html              # Interactive HTML dashboard (open in browser)
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
    ├── hero_base.png         # Copied from input (reused ♻)
    ├── instagram_square/
    │   ├── creative_en.jpg
    │   └── creative_es.jpg
    └── ...
```

---

## CLI Reference

```bash
# Generate creatives
adforge generate <BRIEF> [OPTIONS]
  -i, --input-dir       Input assets directory (default: input_assets)
  -o, --output-dir      Output directory (default: output)
  --mock                Force mock image generation
  -p, --provider        Force provider: firefly | dalle | mock
  -t, --template        Force template: product_hero | editorial | split_panel | minimal | bold_type
  --no-analysis         Skip brief analysis stage
  --no-parallel         Disable parallel hero generation
  -w, --workers         Thread pool size (default: 4)
  -v, --verbose         Debug logging

# Analyze brief quality
adforge analyze <BRIEF> [--llm]

# Validate brief schema
adforge validate <BRIEF>

# List providers
adforge providers
```

---

## Tests

**139 tests** across 9 test modules:

```bash
python -m pytest tests/ -v
```

| Module | Tests | Coverage |
|--------|-------|----------|
| `test_models.py` | Schema enforcement, validation rules | 14 |
| `test_generator.py` | Mock generation, dimensions, determinism | 7 |
| `test_compositor.py` | Composition, text rendering, branding | 14 |
| `test_validator.py` | Brand colors, logo, text, legal | 17 |
| `test_pipeline.py` | End-to-end integration | 12 |
| `test_storage.py` | File management | 5 |
| `test_providers.py` | Provider abstraction, factory | 14 |
| `test_analyzer.py` | Brief scoring, enrichment, risks | 17 |
| `test_templates.py` | Template rendering, auto-selection | 14 |
| `test_tracker.py` | Metrics tracking, serialization | 4 |

---

## Key Design Decisions

### 1. Firefly-First Provider Architecture
Even without Firefly credentials in this assessment, the provider abstraction shows production intent. Swapping DALL-E for Firefly is a config change, not a refactor. The `FireflyProvider` models the actual API — generate, expand, fill, style reference.

### 2. GenAI as Judgment, Not Just Generation
The brief analyzer uses AI to evaluate strategy, not just produce pixels. This shows that a creative technologist uses GenAI thoughtfully — the LLM identifies weak briefs, suggests improvements, and enriches prompts before a single image is generated.

### 3. Template System Over Single Layout
Real creative teams use different layouts for different placements. Auto-selection based on content signals (luxury → minimal, vertical → split panel) encodes creative judgment into the pipeline.

### 4. Parallel Generation
Heroes are generated concurrently across aspect ratios using ThreadPoolExecutor. This matters for production throughput and demonstrates async-aware engineering.

### 5. Cost Tracking From Day One
Every stage is timed and costed. Client-facing creative automation needs cost visibility — per campaign, per asset, per API call. The tracker is wired into the JSON and HTML reports.

### 6. Composition Over Text-in-Image
Campaign text is composited via Pillow, not baked into GenAI prompts. This gives precise typographic control, exact message fidelity, and language switching without regenerating images.

---

## Production Extension Points

| Integration | Current | Production |
|-------------|---------|------------|
| **Image Generation** | DALL-E 3 / Mock | Adobe Firefly Services |
| **Asset Storage** | Local filesystem | AEM DAM / S3 / Azure Blob |
| **Brief Management** | YAML files | Adobe GenStudio / Custom CMS |
| **Translation** | Curated lookup table | TMS (Smartling / Transifex) |
| **Brand Assets** | Local files | Creative Cloud Libraries |
| **Compositing** | Pillow | Photoshop API / Express |
| **Approval** | Manual review | Slack/email workflows |
| **Analytics** | HTML report | Ad platform APIs + dashboards |
| **Deployment** | CLI | App Builder + webhooks |

---

## What I'd Say in the Interview

> "AdForge is deliberately scoped as a proof of concept. The architecture decisions — provider abstraction, brief analysis, template system, cost tracking — are chosen to show how I'd build this for a real client, not just for a demo. Every module has a clear production extension point, and every design choice has a reason I can defend."

For the full post-mortem and evolution story, see [LEARNINGS.md](./LEARNINGS.md).

---

## License

MIT
