# AdForge Interview Prep — Self-Critique & Code Navigation Guide

## Quick-Reference: Where Things Are

Use function and class names as anchors during the interview; line numbers drift as the code evolves.

| "Show me where..." | File | Anchor | Key Detail |
|---|---|---|---|
| Prompt is designed | `src/pipeline.py` | `_build_prompt()` | Concatenates product, brand, colors, audience, keywords, and analyzer enrichment |
| Logo default behavior | `src/compositor.py` | `Compositor._place_logo()` | Top-right corner, 12% of shorter dimension, 4% padding |
| Provider chain resolves | `src/providers.py` | `get_provider()` | Firefly -> Gemini -> Mock auto-detect; DALL-E is explicit selection only |
| Retry/backoff logic | `src/providers.py` | `_retry_api_call()` | Uses `_is_transient_error()` + `_exponential_backoff()` |
| Pydantic validation | `src/models.py` | `CampaignBrief`, `BrandGuidelines` | Hex color regex, ISO languages, min 2 products, min 3 ratios |
| Template auto-selection | `src/templates.py` | `auto_select_template()` | luxury->MINIMAL, short->BOLD, 9:16->SPLIT, long->EDITORIAL |
| Brand compliance checks | `src/validator.py` | `BrandComplianceChecker.full_check()` | Pixel sampling every 10th pixel, logo region check, prohibited words |
| Parallel hero generation | `src/pipeline.py` | `_generate_product_heroes()` | `ThreadPoolExecutor(max_workers=4)` with `as_completed()` |
| Text rendering (no AI) | `src/compositor.py` | `Compositor.compose()` | Pillow text overlay with shadow, wrapping, gradient |
| Translation approach | `src/compositor.py` | `TranslationProvider.translate()` | Curated lookup table, not machine translation |
| Firefly IMS OAuth | `src/providers.py` | `FireflyProvider._get_access_token()` | `client_credentials` grant with token caching |
| Pipeline entry point | `src/pipeline.py` | `run_pipeline()` | Orchestrates all 7 stages |
| Cost tracking | `src/tracker.py` | `StageMetrics`, `AssetMetrics` | Dataclasses used by `PipelineTracker` |
| Mock provider | `src/providers.py` | `MockProvider.generate()` | Deterministic procedural images using brand colors from prompt |

---

## Criterion 1: Ownership & Familiarity

### Q: "Walk me through the architecture."
**Answer:** "AdForge is an 11-module Python pipeline that transforms a campaign brief YAML into localized ad creatives. Data flows: CLI or Streamlit entry -> Pydantic validation (`models.py`) -> brief quality scoring (`analyzer.py`) -> parallel hero image generation via GenAI providers (`providers.py`) -> deterministic text composition via Pillow (`compositor.py` + `templates.py`) -> pixel-level brand compliance checks (`validator.py`) -> multi-format reporting (`report.py`). The provider abstraction (ABC + Factory) decouples generation from orchestration — swapping Firefly for Gemini is a config change."

### Q: "How did you design the prompt?"
**Answer:** "`_build_prompt()` in `src/pipeline.py`. It concatenates product name, description, brand, campaign message, tagline, visual theme, brand color palette (hex codes embedded in text), target audience and region, and visual keywords. Key design choice: the prompt explicitly says not to include text, watermarks, or logos in the image because text is composited via Pillow later. That avoids GenAI text hallucination and lets the same hero support multiple languages."

### Q: "What's the default behavior of the logo?"
**Answer:** "`Compositor._place_logo()` in `src/compositor.py`. Logo is placed in the top-right corner. Size is capped at 12% of the shorter image dimension. Padding is 4% of the canvas width from the top and right edge. The logo is pasted as RGBA with alpha, and `self.logo_placed` is set on success so the validator can cross-check placement."

### Q: "How does a brief become 18 assets?"
**Answer:** "3 products x 3 aspect ratios x 2 languages = 18. Stage 4 generates heroes in parallel (one per product per ratio = 9 API calls). Stage 5 composites each hero with text in each language (9 heroes x 2 languages = 18 composited assets). Each gets brand compliance checks in stage 6."

---

## Criterion 2: Real-Time Problem Solving

### Q: "How would you make template selection configurable per-product?"
**Answer:** "Currently `auto_select_template()` is called during composition, per product and ratio. To make it per-product: (1) Add optional `template: LayoutTemplate` field to the Product model in `models.py`. (2) In `_compose_product_assets()` in `src/pipeline.py`, check `product.template` before falling back to auto-select. (3) Tradeoff: more flexibility for creative teams vs. more complex briefs. I'd default to auto-select and allow override."

### Q: "The composition loop is sequential. How would you speed it up?"
**Answer:** "In `_compose_product_assets()` in `src/pipeline.py`, languages are processed sequentially. I'd wrap that loop in a ThreadPoolExecutor similar to `_generate_product_heroes()`. Caveat: Pillow Image objects aren't thread-safe, so each thread needs its own copy of the hero. Expected ~3-5x speedup for multi-language campaigns (2 products x 3 ratios x 4 languages = 24 sequential compositions that could parallelize)."

### Q: "How would you add a new provider like Stability AI?"
**Answer:** "60 lines, zero changes to pipeline or compositor. (1) Create `StabilityProvider(ImageProvider)` implementing `generate()`, `is_available()`, `provider_type`, `model_name`. (2) Add `STABILITY = 'stability'` to `ProviderType` enum. (3) Add explicit selection block in `get_provider()`. (4) Decide auto-detect priority. The ABC contract guarantees the pipeline doesn't care which provider generated the hero."

---

## Criterion 3: Software Engineering Fundamentals

### Q: "Explain your error handling strategy."
**Answer:** "`_retry_api_call()` in `src/providers.py` uses exponential backoff with jitter. `_is_transient_error()` classifies errors: retries ConnectionError, TimeoutError, HTTP 429, and 5xx; does not retry ValueError or 4xx. Backoff formula: `delay = min(base * 2^attempt + random jitter, max_delay)`. Max 3 retries, 30s max delay. Hero generation failures don't crash the pipeline; `_record_hero_generation_failure()` in `src/pipeline.py` records them as warnings."

**Self-critique:** "No custom exception hierarchy — all RuntimeError/ValueError. I'd add `AdForgeError -> ProviderError, ValidationError, CompositionError`. Also no circuit breaker — if a provider is down, we hammer it with retries on every asset instead of failing fast after N consecutive failures."

### Q: "What design patterns did you use?"
**Answer:** "(1) Abstract Factory — `ImageProvider` ABC + `get_provider()` factory in `src/providers.py`. (2) Strategy — 5 template renderers in `TEMPLATE_RENDERERS`, selected at runtime by `auto_select_template()`. (3) Pipeline/Stages — 7 sequential stages with per-stage metrics. (4) Context Manager — `PipelineTracker._StageContext` for automatic timing. (5) Dataclass aggregates — `GenerationMetadata`, `PipelineServices` bundle collaborators."

### Q: "What about queueing patterns or DLQs?"
**Answer:** "Currently `ThreadPoolExecutor` with `as_completed()` is used in `_generate_product_heroes()` for parallelism. Failed heroes are logged to `result.warnings` but not persisted for retry, which is a gap. For production I'd add: (1) A dead-letter queue (JSON file or Redis) for failed assets. (2) A retry command: `adforge retry --from-dlq output/failures.json`. (3) Semaphores per provider to prevent rate-limit storms."

---

## Criterion 4: Applied AI & Multimodal

### Q: "Where do you use AI vs. traditional engineering?"
**Answer:**

| Component | AI? | Tool | Why |
|---|---|---|---|
| Hero image generation | Yes | Firefly/Gemini/DALL-E | Core creative output — can't do without GenAI |
| Brief quality scoring | Yes (optional) | GPT-4o-mini | Strategic judgment before burning GPU budget |
| Text rendering | **No** | Pillow | Deterministic, no hallucination, instant language switch |
| Template selection | **No** | Heuristic rules | $0, 0ms, fully auditable |
| Translation | **No** | Lookup table | Ad copy needs human review, not machine MT |
| Brand compliance | **No** | Pixel sampling + string match | Verifiable, no model drift, no false negatives |
| Retry logic | **No** | Exponential backoff | Deterministic recovery |

"The principle: use AI when judgment or creativity is needed. Use traditional engineering when you need precision, auditability, or determinism."

### Q: "What are the limitations of your AI integration?"
**Answer:** "(1) No vision model to assess generated image quality — we trust the prompt. (2) Brief analyzer fallback to heuristics is simplistic when no LLM key is available. (3) Brand color embedding in prompts is best-effort — models don't always respect color instructions. (4) Firefly's style reference (strength=60) is a balance but not guaranteed to maintain brand consistency."

---

## Criterion 5: Adobe Ecosystem

### Q: "Walk me through your Firefly integration."
**Answer:** "`FireflyProvider` in `src/providers.py`. It uses IMS OAuth 2.0 `client_credentials` with token caching that refreshes shortly before expiry. Generation uses `POST /v3/images/generate` with `contentClass: 'photo'` and `presets: ['photo_real']`. Generative Expand uses `POST /v3/images/expand` for aspect-ratio adaptation without cropping artifacts. Style reference passes a brand asset as base64 with `strength: 60`."

**Self-critique:** "Token refresh isn't wrapped in retry logic — a transient IMS error would fail the entire run. I'd wrap `_get_access_token()` in `_retry_api_call()`."

### Q: "How would this extend to production Adobe workflows?"
**Answer:** "README section 8 documents extension points: (1) AEM DAM replaces local filesystem for asset storage. (2) GenStudio for performance content at scale. (3) App Builder for event-driven pipeline triggers via webhooks. (4) Creative Cloud Libraries for brand asset management. The provider abstraction is ready — GenStudio would be another provider implementing the same interface."

---

## Criterion 6: Implementation Quality

### Q: "What would you improve about the code structure?"
**Answer (lead with self-critique):**
- "`app.py` is 2,133 lines — it's a monolith. I'd extract to `ui/pages/` and `ui/components/` with separate CSS."
- "Templates share ~30% boilerplate in logo placement and text rendering. I'd extract `_place_logo()` and `_render_text_block()` as shared helpers."
- "Local filesystem storage won't scale horizontally. I'd abstract behind a `StorageBackend` interface with S3/AEM DAM adapters."
- "Font paths are hardcoded per-OS in `src/compositor.py`. Breaks in Docker. I'd use fontconfig or bundled fonts."

---

## Criterion 7: Mentorship & Knowledge Transfer

### Q: "How would you onboard a junior developer?"
**Answer:** "(1) Start with `models.py` — the data contract, Pydantic validation shows how to catch bugs at the boundary. (2) Follow the 7 stages in `pipeline.py` as a roadmap. (3) Run `just test` — 152 tests pass, showing the test-driven approach. (4) First PR: add a new template to `templates.py` — low risk, high visibility, teaches the Strategy pattern. (5) Architecture diagram at `docs/architecture.png`. (6) Study guide at `docs/study-guide.md`."

### Q: "Give a code review example."
**Answer:** "In `validator.py:208`, `if w in all_text` is substring matching. I'd flag: 'cure' inside 'pedicure' is a false positive. Fix: `re.search(r'\b' + re.escape(w) + r'\b', all_text)`. This teaches word-boundary regex and false positive rates in content moderation. I'd pair on the fix and explain why `re.escape()` prevents regex injection."

---

## Criterion 8: AI vs Traditional Engineering

### Q: "When should you NOT use an LLM?"
**Answer from this codebase:** "(1) Text rendering — Pillow is deterministic, LLMs produce gibberish. (2) Template selection — $0 heuristics vs $0.01 LLM calls, faster and auditable. (3) Compliance — substring matching is verifiable, LLMs might hallucinate 'text is fine.' (4) Translation — lookup table gives exact control over ad copy. (5) Color validation — pixel sampling is mathematical, not probabilistic. The principle: AI for creativity and judgment, engineering for precision and auditability."

---

## Criterion 9: Attention to Detail — Self-Critique Matrix

| Issue | Where | Severity | What I'd Fix |
|---|---|---|---|
| ~~Dead code (generator.py)~~ | ~~`src/generator.py`~~ | ~~Critical~~ | ~~Deleted~~ |
| ~~Stale provider chain comments~~ | ~~`src/pipeline.py`, `src/cli.py`~~ | ~~Medium~~ | ~~Fixed~~ |
| app.py monolith | `src/app.py` (2,133 lines) | High | Extract to multi-page Streamlit with `ui/` module |
| No custom exceptions | Throughout | Medium | `AdForgeError` hierarchy |
| No circuit breaker | `src/providers.py` | Medium | CircuitBreaker class with half-open state |
| No DLQ | `src/pipeline.py` | Medium | JSON-based dead letter queue for failed assets |
| Substring matching | `src/validator.py:208` | Medium | Word-boundary regex `\b...\b` |
| Sequential composition | `src/pipeline.py` (`_compose_product_assets`) | Medium | ThreadPoolExecutor with per-thread image copies |
| Hardcoded font paths | `src/compositor.py` | Medium | fontconfig or bundled fonts |
| Token refresh not retried | `src/providers.py` (`FireflyProvider._get_access_token`) | Low | Wrap in `_retry_api_call()` |
| Local-only storage | `src/storage.py` | Low | StorageBackend interface with S3/AEM DAM |
| Pillow getdata() deprecated | `src/validator.py:89,174` | Low | Switch to `get_flattened_data()` |

---

## Test Coverage Summary

**152 tests passing across 10 test files.**

| Area | Tests | Coverage Notes |
|---|---|---|
| Providers (factory, fallback, all 4 providers) | 25 | Strong |
| Validator (colors, logo, words, legal, aggregation) | 20 | Strong |
| Models (schema, duplicates, ISO languages) | 18 | Strong |
| Compositor (text, gradients, translations) | 18 | Strong |
| Templates (auto-select, all 5 layouts) | 17 | Strong |
| Analyzer (heuristic, LLM, enrichment) | 17 | Strong |
| Pipeline (end-to-end, asset count, compliance) | 15 | Strong |
| Analytics (KPIs, winner detection) | 11 | Strong |
| Storage (files, slugs) | 7 | Adequate |
| Tracker (metrics, serialization) | 4 | Adequate |
| **App UI** | **0** | **Intentionally excluded — Streamlit is hard to unit test** |
