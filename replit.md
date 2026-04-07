# AdForge — Creative Automation Pipeline

## Overview
AdForge is a creative automation pipeline that generates localized social media ad creatives from a single campaign brief. It automates the process of ingesting a brief, analyzing its quality, resolving or generating product "hero" images using GenAI, composing them into various aspect ratios with brand-consistent layouts, and validating the final output for brand compliance and legal requirements.

## Architecture
- **Language:** Python 3.12
- **Frontend:** Streamlit web UI (`src/app.py`)
- **Port:** 5000 (configured in `.streamlit/config.toml`)

## Key Modules
- `src/app.py` — Streamlit web UI for campaign management and approval
- `src/pipeline.py` — Central orchestrator for the 7-stage execution flow
- `src/providers.py` — GenAI provider abstractions (Adobe Firefly, DALL-E 3, Gemini, Mock)
- `src/compositor.py` — Image composition logic using Pillow
- `src/templates.py` — Layout templates (Product Hero, Editorial, Split Panel, etc.)
- `src/analyzer.py` — Campaign brief quality scoring
- `src/validator.py` — Brand and legal compliance checks
- `src/cli.py` — Command-line interface

## GenAI Providers (optional, app works without them in mock mode)
- Adobe Firefly: `FIREFLY_CLIENT_ID`, `FIREFLY_CLIENT_SECRET`
- Google Gemini: `GEMINI_API_KEY`
- OpenAI DALL-E 3: `OPENAI_API_KEY`

## Running the App
```
streamlit run src/app.py
```

The workflow "Start application" is configured to run this automatically.

## Package Management
- `pip` with `requirements.txt`
- Key packages: streamlit, Pillow, pydantic, openai, google-genai, rich, click, pyyaml
