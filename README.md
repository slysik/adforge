<![CDATA[<div align="center">

# 🎨 AdForge

### Creative Automation Pipeline for Localized Social Campaigns

**Generate dozens of on-brand, localized ad creatives from a single campaign brief — in seconds.**

[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-158%20passing-brightgreen.svg)](#tests)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

</div>

---

## 🏖️ The Client Scenario

**Client:** [BlueBeachHouseDesigns.com](https://bluebeachhousedesigns.com) — A Charleston, SC handcrafted shell artist launching hundreds of localized social ad campaigns targeted to Southern Florida interior designers monthly.

**Challenge:** Manually creating and localizing creative variants for hundreds of campaigns per month is slow, expensive, and error-prone.

**Solution:** AdForge automates the entire creative pipeline — from campaign brief to validated, localized ad creatives ready for Instagram, Stories/Reels, and Facebook.

<div align="center">

### One Brief → 18 Campaign-Ready Creatives in 4.2 Seconds

</div>

---

## ✨ Pipeline at a Glance

```
                          ┌─────────────────────────────────────┐
                          │         CAMPAIGN BRIEF (YAML)       │
                          │  Products • Audience • Brand Rules  │
                          └──────────────┬──────────────────────┘
                                         │
                    ┌────────────────────┐│┌────────────────────┐
                    │  📂 Input Assets   │││  🤖 GenAI Provider │
                    │  (reuse existing)  ├┤│  (generate new)    │
                    └────────────────────┘│└────────────────────┘
                                         ▼
┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐
│ 📋       │  │ 🔍       │  │ 📂       │  │ 🎨       │  │ 🖼️       │  │ ✅       │  │ 📊       │
│ INGEST   │→ │ ANALYZE  │→ │ RESOLVE  │→ │ GENERATE │→ │ COMPOSE  │→ │ VALIDATE │→ │ REPORT   │
│          │  │          │  │          │  │          │  │          │  │          │  │          │
│ Parse &  │  │ Score    │  │ Find     │  │ Create   │  │ Layout   │  │ Brand    │  │ Console  │
│ validate │  │ brief    │  │ existing │  │ missing  │  │ template │  │ colors   │  │ JSON     │
│ brief    │  │ quality  │  │ heroes   │  │ heroes   │  │ + text   │  │ logo     │  │ HTML     │
│          │  │ 92/100   │  │ or mark  │  │ via      │  │ + logo   │  │ legal    │  │ dashboard│
│          │  │          │  │ for gen  │  │ GenAI    │  │ + i18n   │  │ words    │  │          │
└──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘  └──────────┘
```

**3 products × 3 aspect ratios × 2 languages = 18 creatives** — all brand-compliant, localized, and organized.

---

## 🖼️ Sample Output

> Generated from the Blue Beach House Designs campaign brief using real product photography.

### Resort Shell Handbag — All 3 Aspect Ratios (English)

| Instagram 1:1 | Stories/Reels 9:16 | Facebook 16:9 |
|:---:|:---:|:---:|
| ![1:1](sample_output/coastal_collection_2025/resort-shell-handbag/instagram_square/creative_en.jpg) | ![9:16](sample_output/coastal_collection_2025/resort-shell-handbag/stories_reels/creative_en.jpg) | ![16:9](sample_output/coastal_collection_2025/resort-shell-handbag/facebook_landscape/creative_en.jpg) |
| Editorial layout | Split panel layout | Editorial layout |

### Localized Variants — Spanish 🇪🇸

| Cowrie Shell Box (ES) | Painted Shell Art (ES) |
|:---:|:---:|
| ![cowrie-es](sample_output/coastal_collection_2025/cowrie-shell-box/instagram_square/creative_es.jpg) | ![painted-es](sample_output/coastal_collection_2025/painted-shell-art/instagram_square/creative_es.jpg) |

<details>
<summary><b>📁 Full output folder structure</b></summary>

```
output/coastal_collection_2025/
├── report.json                    # Machine-readable results + metrics
├── report.html                    # Interactive HTML dashboard
├── resort-shell-handbag/
│   ├── hero_base.png              # Reused from input_assets/ ♻️
│   ├── instagram_square/
│   │   ├── creative_en.jpg        # 1080×1080, English
│   │   └── creative_es.jpg        # 1080×1080, Spanish
│   ├── stories_reels/
│   │   ├── creative_en.jpg        # 1080×1920, English
│   │   └── creative_es.jpg        # 1080×1920, Spanish
│   └── facebook_landscape/
│       ├── creative_en.jpg        # 1920×1080, English
│       └── creative_es.jpg        # 1920×1080, Spanish
├── cowrie-shell-box/
│   └── ... (same structure)
└── painted-shell-art/
    └── ... (same structure)
```

</details>

---

## 🚀 Quick Start (3 Steps)

### Prerequisites
- Python 3.9+
- No API keys needed for demo (mock mode works out of the box)

```bash
# 1. Clone & install
git clone https://github.com/slysik/adforge.git && cd adforge
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 2. Generate sample input assets (creates logo + product images)
python create_sample_assets.py

# 3. Run the pipeline
python -m src.cli generate sample_briefs/beach_house_campaign.yaml --mock
```

**That's it.** Open `output/coastal_collection_2025/report.html` in your browser to see the interactive dashboard.

### Optional: Web UI

```bash
streamlit run src/app.py
```

### Optional: Real GenAI Providers

```bash
# Google Imagen 4.0 (recommended — free tier available)
export GEMINI_API_KEY=your-key
python -m src.cli generate sample_briefs/beach_house_campaign.yaml

# Adobe Firefly Services (production)
export FIREFLY_CLIENT_ID=your-id
export FIREFLY_CLIENT_SECRET=your-secret
python -m src.cli generate sample_briefs/beach_house_campaign.yaml -p firefly

# OpenAI DALL-E 3
export OPENAI_API_KEY=sk-your-key
python -m src.cli generate sample_briefs/beach_house_campaign.yaml -p dalle
```

---

## 📋 Campaign Brief Example

The pipeline accepts YAML or JSON briefs. Here's the Blue Beach House Designs brief ([full file](sample_briefs/beach_house_campaign.yaml)):

```yaml
campaign:
  name: "Coastal Collection 2025"
  brand: "Blue Beach House Designs"
  message: "The perfect shell handbag for the season..."
  tagline: "Handcrafted Coastal Elegance"
  target_region: "Southern Florida — Naples & Palm Beach"
  target_audience: "Home decor designers, interior stylists, ages 30-60"
  languages: [en, es]

  brand_guidelines:
    primary_colors: ["#1B4F72", "#F5E6CA", "#FFFFFF"]
    accent_color: "#D4A574"
    font_family: "Georgia"
    logo_path: "input_assets/logo.png"
    prohibited_words: ["cheap", "fake", "plastic", "mass-produced"]
    required_disclaimer: "Custom orders welcome — bluebeachhousedesigns.com"

  products:
    - id: "resort-shell-handbag"
      name: "Resort Shell Handbag"
      hero_image: "input_assets/resort-shell-handbag.png"   # ♻️ reused
      keywords: [shell handbag, rattan bag, coastal fashion]

    - id: "cowrie-shell-box"
      name: "Bespoke Rattan Cowrie Shell Box"
      hero_image: "input_assets/bespoke-rattan-cowrie-shell-box.png"

    - id: "painted-shell-art"
      name: "Painted Shell Art"
      hero_image: "input_assets/painted-shell-art.png"

  aspect_ratios:
    - { name: instagram_square,    ratio: "1:1",  width: 1080, height: 1080 }
    - { name: stories_reels,       ratio: "9:16", width: 1080, height: 1920 }
    - { name: facebook_landscape,  ratio: "16:9", width: 1920, height: 1080 }
```

---

## 🔍 Brief Analysis Engine

Before generating anything, AdForge scores the brief on 4 dimensions and provides actionable recommendations:

```
╭──────────── Brief Analysis ─────────────╮
│ Brief Quality Score: 92/100 (A)         │
│   [██████████████████░░]                │
│                                         │
│   Completeness:   25/25  ████████████   │
│   Clarity:        20/25  ████████░░░░   │
│   Brand Strength: 25/25  ████████████   │
│   Targeting:      22/25  ██████████░░   │
╰─────────────────────────────────────────╯

✓ Strengths:
  • 3 products defined
  • Multi-language campaign (en, es)
  • Hyper-local region targeting: Southern Florida — Naples & Palm Beach
  • Brand palette defined (3 colors) + accent color
  • Logo asset provided
  • Prohibited words list (4 terms)
  • Legal disclaimer configured
  • Full platform coverage: Instagram, Stories/Reels, Facebook/YouTube

🎨 Creative Direction: seasonal, coastal/nautical, design-professional visual language
```

This demonstrates **GenAI as a judgment tool** — the AI evaluates strategy, not just generates pixels.

---

## 🎭 Layout Templates

5 composition templates, auto-selected by content signals:

| Template | When Auto-Selected | Visual |
|:---------|:-------------------|:-------|
| **Product Hero** | Default — universally safe | Full-bleed hero + gradient + bottom text |
| **Editorial** | Long messages (>40 chars) | 60/40 hero/text split with brand panel |
| **Split Panel** | Vertical formats (9:16) | 50/50 image + branded text panel |
| **Minimal** | Luxury/premium keywords | Centered hero, generous whitespace |
| **Bold Type** | Short punchy messages (≤20 chars) | Oversized typography on tinted hero |

```python
# Auto-selection logic (encoded creative judgment)
if luxury_keywords:    → MINIMAL       # "premium", "gold", "velvet"
if short_message:      → BOLD_TYPE     # ≤20 characters
if vertical_format:    → SPLIT_PANEL   # 9:16 stories/reels
if long_message:       → EDITORIAL     # >40 characters
else:                  → PRODUCT_HERO  # safe default
```

Override with `--template <name>` on the CLI.

---

## ✅ Brand Compliance & Legal Checks

Every generated creative is validated before delivery:

| Check | Method | What It Catches |
|:------|:-------|:----------------|
| **Brand Colors** | Pixel sampling (every 10th pixel) | Missing palette colors in final image |
| **Logo Presence** | Compositor flag + pixel verification in top-right region | Logo file missing, paste failed, region empty |
| **Prohibited Words** | String match against ALL rendered text | Brief-specific banned terms ("cheap", "fake", etc.) |
| **Legal Terms** | Regulatory term flagging | "guaranteed", "miracle", "cure", "#1", "risk-free", etc. |

Results are embedded in every asset's metadata:
```json
"brand_compliance": {
  "status": "passed",
  "notes": [
    "[Colors] All brand colors detected in image.",
    "[Logo] Logo verified in top-right region (16641/16641 opaque pixels).",
    "[Text] No prohibited words detected. Checked 4 rendered text(s)."
  ]
}
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CLI (click)  /  Web UI (Streamlit)                   │
└───────────────────────────┬─────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────────────┐
│                    Pipeline Orchestrator (pipeline.py)                   │
│    Ingest → Analyze → Resolve → Generate → Compose → Validate → Report │
└──┬────┬────┬────┬────┬────┬────┬────────────────────────────────────────┘
   │    │    │    │    │    │    │
   ▼    ▼    ▼    ▼    ▼    ▼    ▼
 Models Analyzer Provider Templates Compositor Validator Report
 (Pydantic) (scoring) (abstraction) (5 layouts) (Pillow) (brand+legal) (JSON+HTML)
                  │
        ┌─────────┼─────────┬──────────┐
        ▼         ▼         ▼          ▼
    Firefly    Imagen    DALL-E 3    Mock
    Services   4.0                  (testing)
```

### Module Inventory (11 modules, ~2,400 lines)

| Module | Purpose |
|:-------|:--------|
| `models.py` | Pydantic schemas — validates briefs, enforces ≥2 products, hex colors, ISO languages |
| `pipeline.py` | 7-stage orchestrator — parallel generation, progress bars, metrics |
| `providers.py` | Provider abstraction — Firefly → Gemini → DALL-E → Mock auto-resolution |
| `analyzer.py` | Brief quality scoring — heuristic + optional LLM augmentation |
| `templates.py` | 5 layout templates — auto-selected by content, ratio, and keywords |
| `compositor.py` | Image composition — resize, text overlay, logo, gradient, translation |
| `validator.py` | Brand compliance — color pixels, logo region, prohibited words, legal flags |
| `storage.py` | File management — organized output, hero discovery, asset reuse |
| `tracker.py` | Performance metrics — per-stage timing, API call counting, cost estimation |
| `report.py` | Reporting — Rich console, JSON, interactive HTML dashboard |
| `analytics.py` | Performance analytics — sample KPIs, CTR/CPA calculations, winner detection |

---

## 🔌 Provider Architecture

```
┌──────────────────────────────────────────────────────────┐
│                ImageProvider (ABC)                        │
│         generate() → (PIL Image, Metadata)               │
└────────┬────────┬────────┬────────┬──────────────────────┘
         │        │        │        │
   ┌─────▼──┐ ┌───▼───┐ ┌──▼────┐ ┌▼──────┐
   │Firefly │ │Imagen │ │DALL-E │ │ Mock  │
   │Services│ │4.0    │ │3      │ │       │
   │        │ │       │ │       │ │$0.00  │
   │$0.04/  │ │Native │ │$0.04/ │ │       │
   │image   │ │aspect │ │image  │ │Determ-│
   │        │ │ratios │ │       │ │inistic│
   │Generate│ │       │ │3 fixed│ │No API │
   │Expand  │ │       │ │sizes  │ │needed │
   │Fill    │ │       │ │       │ │       │
   └────────┘ └───────┘ └───────┘ └───────┘
```

**Auto-resolution:** Firefly → Gemini → Mock (pipeline always runs, degrades gracefully).

The `FireflyProvider` models the actual Firefly Services REST API:
- **Text-to-Image** (`/v3/images/generate`) — primary hero generation
- **Generative Expand** (`/v3/images/expand`) — aspect-ratio adaptation without crop artifacts
- **Style Reference** — brand-consistent generation from reference images
- **IMS Authentication** — `client_credentials` grant with automatic token refresh

---

## 📊 Performance Tracking

Every pipeline run tracks timing, cost, and provider details:

```
                          Pipeline Performance
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━┳━━━━━━━┳━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Stage                         ┃ Time ┃ Items ┃ API Calls ┃ Est. Cost ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━╇━━━━━━━╇━━━━━━━━━━━╇━━━━━━━━━━━┩
│ brief_ingestion               │  5ms │     1 │         0 │         – │
│ brief_analysis                │  0ms │     1 │         0 │         – │
│ compose_resort-shell-handbag  │ 1.4s │     6 │         0 │         – │
│ validate_resort-shell-handbag │ 1.4s │     6 │         0 │         – │
│ compose_cowrie-shell-box      │ 1.4s │     6 │         0 │         – │
│ validate_cowrie-shell-box     │ 1.4s │     6 │         0 │         – │
│ compose_painted-shell-art     │ 1.4s │     6 │         0 │         – │
│ validate_painted-shell-art    │ 1.4s │     6 │         0 │         – │
│ TOTAL                         │ 4.2s │       │         0 │    $0.000 │
└───────────────────────────────┴──────┴───────┴───────────┴───────────┘
```

---

## 🌐 Web UI

```bash
streamlit run src/app.py
```

The Streamlit web interface provides:
- **📋 Campaign overview** — brief metadata, analysis scores, product details
- **🖼️ Creative gallery** — side-by-side ratio comparison per product with compliance badges
- **✅ Approval queue** — per-asset approve/reject workflow with comments + JSON export
- **📈 Performance analytics** — sample KPIs with CTR, CPA, winner detection
- **📊 Pipeline metrics** — stage timing, cost breakdown, provider info
- **🚀 Live execution** — run the pipeline from the browser with any provider

---

## 🧪 Tests

**158 tests** across 10 test modules:

```bash
python -m pytest tests/ -v
```

| Module | What It Tests | Count |
|:-------|:-------------|------:|
| `test_models.py` | Schema enforcement, Pydantic validation | 14 |
| `test_generator.py` | Mock generation, dimensions, determinism | 7 |
| `test_compositor.py` | Composition, text rendering, branding | 14 |
| `test_validator.py` | Brand colors, logo, text, legal | 17 |
| `test_pipeline.py` | End-to-end integration | 12 |
| `test_storage.py` | File management, slug generation | 5 |
| `test_providers.py` | Provider abstraction, factory, fallback | 14 |
| `test_analyzer.py` | Brief scoring, enrichment, risk flags | 17 |
| `test_templates.py` | Template rendering, auto-selection | 14 |
| `test_tracker.py` | Metrics tracking, serialization | 4 |
| `test_analytics.py` | KPI generation, winner detection | 40 |

---

## 🧠 Key Design Decisions

### 1. Firefly-First Provider Architecture
The provider abstraction models a production deployment where Adobe Firefly Services is the primary generator. Swapping any provider is a config change, not a refactor. The `FireflyProvider` implements the actual v3 API spec.

### 2. GenAI as Judgment, Not Just Generation
The brief analyzer uses AI to evaluate strategy quality before a single image is generated. It scores completeness, identifies weak messaging, suggests improvements, and enriches prompts with audience/region context. This shows GenAI applied thoughtfully.

### 3. Template System Over Single Layout
Real creative teams use different layouts for different placements. Auto-selection based on content signals (luxury → minimal, vertical → split panel) encodes creative judgment into code.

### 4. Composition Over Text-in-Image
Campaign text is composited via Pillow, not baked into GenAI prompts. This gives exact typographic control, precise message fidelity, and instant language switching without regenerating images.

### 5. Parallel Generation + Cost Tracking
Heroes are generated concurrently via ThreadPoolExecutor. Every stage is timed and costed. Client-facing creative automation needs cost visibility from day one.

### 6. Contrast-Safe Panel Colors
The split-panel template automatically selects the darkest brand color (by luminance) for text panels, guaranteeing readable white text regardless of the brand's color palette.

---

## 🔮 Production Extension Points

| Capability | Current (POC) | Production |
|:-----------|:-------------|:-----------|
| Image Generation | Mock / Gemini / DALL-E | Adobe Firefly Services |
| Asset Storage | Local filesystem | AEM DAM / S3 / Azure Blob |
| Brief Management | YAML files | Adobe GenStudio / CMS |
| Translation | Curated lookup table | TMS (Smartling / Transifex) |
| Brand Assets | Local files | Creative Cloud Libraries |
| Compositing | Pillow | Photoshop API / Express |
| Approval | Web UI queue | Workfront / Slack workflows |
| Analytics | Sample KPIs | Ad platform APIs + dashboards |
| Deployment | CLI / Streamlit | App Builder + webhooks |

---

## 📂 CLI Reference

```bash
# Generate creatives from a brief
python -m src.cli generate <BRIEF> [OPTIONS]
  --mock                Use mock mode (no API keys needed)
  -p, --provider        Force: firefly | gemini | dalle | mock
  -t, --template        Force: product_hero | editorial | split_panel | minimal | bold_type
  -i, --input-dir       Input assets directory (default: input_assets)
  -o, --output-dir      Output directory (default: output)
  --no-analysis         Skip brief analysis
  --no-parallel         Sequential generation
  -w, --workers N       Thread pool size (default: 4)
  -v, --verbose         Debug logging

# Analyze a brief's quality without generating
python -m src.cli analyze <BRIEF> [--llm]

# Validate brief schema
python -m src.cli validate <BRIEF>

# List available providers and their status
python -m src.cli providers
```

---

## 💬 What I'd Say in the Interview

> *"AdForge is deliberately scoped as a proof of concept. The architecture decisions — provider abstraction, brief analysis, template system, cost tracking — are chosen to show how I'd build this for a real client, not just for a demo. Every module has a clear production extension point, and every design choice has a reason I can defend."*

For the full post-mortem and evolution story, see [LEARNINGS.md](./LEARNINGS.md).

---

<div align="center">

**Built for the Adobe FDE – Creative Technologist Assessment**

[ADFORGE_INTENT.md](./ADFORGE_INTENT.md) · [LEARNINGS.md](./LEARNINGS.md) · [EVALUATION.md](./EVALUATION.md)

</div>
]]>