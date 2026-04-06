# AdForge — Learnings & Post-Mortem

A record of what was built, what broke, what was fixed, and what to defend in the interview.

---

## Timeline

### V1: Initial Build (~2 hours)
Built a working end-to-end pipeline: YAML brief → GenAI hero generation → multi-ratio composition → brand/legal validation → reporting. 24 tests, mock mode, two sample campaigns. Everything ran and produced output.

### V2: Code Review Response (~1.5 hours)
Received a thorough 7-finding code review. Every finding was valid. Fixed all 7, expanding from 24 to 83 tests.

---

## The 7 Findings & What I Learned

### Finding 1 (High): Mock heroes had baked-in labels
**What happened:** Mock mode rendered `[MOCK] Product Name` and `Aspect: 1:1` directly into hero images. The pipeline generated all heroes at 1:1 and then cropped them into other ratios. This meant the 9:16 creative visibly showed "Aspect: 1:1" text from the hero bleeding through behind the campaign copy.

**Root cause:** I treated mock mode as "just for testing" and didn't think about it as producing real inputs to the composition stage. The hero is consumed by the compositor — any text baked into it becomes part of the final creative.

**Fix:** 
- Mock images are now clean procedural product silhouettes with zero text (gradient backgrounds, product shape, accent elements)
- Pipeline generates heroes per-ratio instead of one 1:1 hero cropped everywhere
- For reused assets, center-crop is still used (those come from real photography)

**Lesson:** Every stage's output is the next stage's input. Mock mode isn't a throwaway — it's a contract. If mock output has different properties than real output, the downstream stages are tested against the wrong thing.

---

### Finding 2 (High): Brand compliance was theater
**What happened:** Three separate problems:
1. Logo check only verified the source file existed (`Path(logo_path).exists()`), not that the logo was actually rendered in the output image
2. The logo check result was assigned to `_` and thrown away: `_, logo_notes = brand_checker.check_logo_presence(output_path)`
3. Text compliance only checked `brief.message`, not the tagline, disclaimer, or translated text actually rendered on the creative

**Root cause:** I implemented the checks as an afterthought, running them against the brief inputs rather than the rendered outputs. The compliance layer wasn't connected to what the compositor actually did.

**Fix:**
- Logo check now does pixel-level verification in the expected top-right region (checks opaque pixel count + color diversity)
- Compositor sets `self.logo_placed = True` after successful paste; this flag is passed to the validator
- Text compliance now receives `rendered_texts` — every string actually drawn on the creative (message, tagline, brand name, disclaimer, in all languages)
- All check results flow through to the asset record with evidence-backed `ComplianceResult(status, notes)`

**Lesson:** Validation that doesn't inspect the actual artifact is not validation. If the compliance check can pass when the creative is wrong, it's worse than no check — it's a false guarantee. Connect checks to outputs, not inputs.

---

### Finding 3 (Medium): Schema didn't enforce the exercise contract
**What happened:** The Pydantic model accepted:
- A single product (exercise requires 2+)
- Any number of aspect ratios (exercise requires 3+)
- Duplicate product IDs
- Invalid hex color strings like "red" or "blue"
- Arbitrary language codes like "klingon"

**Root cause:** I set `min_length=1` on products out of habit ("at least one") without mapping back to the exercise requirements. Color and language validation weren't added at all.

**Fix:**
- `products: min_length=2`
- `aspect_ratios: min_length=3`
- `@model_validator` for unique product IDs
- `@field_validator` for hex color format (`#RRGGBB` regex)
- `@field_validator` for language codes against a supported set
- Product ID pattern enforced as lowercase slug

**Lesson:** The schema IS the contract. If the README says "at least two products" but the model accepts one, the contract is the model, not the README. Encode business rules in validation, not documentation.

---

### Finding 4 (Medium): Dead configuration fields
**What happened:** The brief schema defined `accent_color`, `font_family`, and `required_disclaimer`. The sample briefs used them. But the compositor ignored all three — it hardcoded generic font lookup and only used `primary_colors[0]` for the accent bar.

**Root cause:** I designed the schema first (the right idea), then implemented the compositor without checking every field was wired through.

**Fix:**
- `accent_color` → used for the bottom accent bar (falls back to `primary_colors[0]`)
- `font_family` → compositor tries family-specific font paths before generic fallbacks
- `required_disclaimer` → rendered as small print near the bottom of every creative, tracked in `rendered_texts`

**Lesson:** Every field in a public schema is a promise. If you define it, wire it. If you can't wire it yet, don't put it in the schema — or mark it explicitly as `# TODO: not yet implemented`.

---

### Finding 5 (Medium): Fake "multi-language support"
**What happened:** The compositor had a `TRANSLATIONS` dict with exactly two English messages pre-translated. For any other message or language, `_translate()` silently returned the original English text. The README claimed "Multi-language support (EN, ES, FR, DE, PT, JA, ZH)."

**Root cause:** I wanted to show localization as a feature but took a shortcut. The silent fallback meant a reviewer changing the campaign message would get English-only output with no indication anything was wrong.

**Fix:**
- Created an explicit `TranslationProvider` class with documented strategy
- `translate()` returns `(text, was_translated)` — callers know if translation succeeded
- Unknown translations return source text with a warning logged and surfaced in the pipeline result
- Warnings suggest "Submit to TMS for review" instead of silently pretending

**Lesson:** Silent fallbacks are lies. If a feature has known boundaries, make the boundaries visible. A translation system that silently returns English is worse than one that says "translation unavailable." The reviewer should never be surprised.

---

### Finding 6 (Medium): Prompt provenance discarded
**What happened:** The `GeneratedAsset` model had a `prompt_used` field. The generator returned the prompt. But the pipeline never stored it — every asset in `report.json` showed `prompt_used: null`.

**Root cause:** A simple wiring miss. The variable was there but never passed through to the model constructor.

**Fix:** One-line fix — pass `prompt_used=hero_prompt` when creating `GeneratedAsset`.

**Lesson:** If you model a field, test that it's populated. This was the easiest fix but also the most embarrassing — it's the kind of thing that makes a reviewer wonder what else was left unfinished.

---

### Finding 7 (Medium): Tests proved creation, not correctness
**What happened:** The pipeline tests checked:
- File counts
- File existence
- That `failed_count == 0`

They did NOT check:
- Output image dimensions
- Whether rendered text matched expectations
- Whether compliance results were evidence-backed
- Whether prompts were persisted
- Whether localization worked or warned
- Whether the disclaimer appeared

**Root cause:** I wrote tests for "does it run" rather than "does it do what it claims."

**Fix:** Expanded from 24 to 83 tests:
- **Model tests:** Schema enforcement (min products, min ratios, duplicate IDs, hex validation, language codes)
- **Generator tests:** Correct dimensions per ratio, prompt content, no text in mock images, deterministic colors
- **Compositor tests:** Output dimensions, rendered text tracking, logo placed flag, accent color rendering, disclaimer presence, translation provider behavior
- **Validator tests:** Color detection accuracy, logo pixel verification, prohibited word detection against rendered text, aggregate worst-status logic, legal flag detection
- **Pipeline tests:** Asset count, prompt persistence, reuse tracking, compliance evidence, JSON round-trip, localized text in Spanish assets, disclaimer in holiday campaign

**Lesson:** A test that only checks "did it not crash" is a smoke test, not a contract test. For an interview deliverable, the tests should prove the claims you make in the README. If you claim "brand compliance checks," test that the checks produce correct results for known inputs.

---

## What I'd Say in the Interview

### On the initial version
"V1 worked end-to-end but had meaningful gaps between what the code claimed and what it actually verified. The compliance layer was more of a sketch than a real check — it ran against inputs rather than outputs. The mock mode was a testing convenience that produced unrealistic inputs for downstream stages."

### On the review response
"Every finding was valid. The most important lesson was that validation should inspect the artifact, not the intent. Logo compliance that checks file existence isn't compliance — it's a config check. Text compliance that checks the brief message but not the rendered translations isn't compliance — it's a spot check on the wrong thing."

### On what I'd still improve
1. **Async pipeline** — parallelize hero generation across products/ratios
2. **Content-aware cropping** — saliency detection for reused hero images
3. **Real translation integration** — DeepL or Google Translate with human review workflow
4. **Template system** — multiple layout templates per aspect ratio
5. **Cloud storage** — S3/Azure Blob with CDN delivery
6. **Approval workflow** — Slack/email notifications for review
7. **A/B variants** — multiple creative options per placement
8. **Cost tracking** — API spend per generation

### On the tradeoffs I'd defend
- **Per-ratio generation vs. single hero:** More API calls, but avoids composition artifacts. In production, you'd use generative fill (Firefly) for ratio adaptation.
- **Pre-approved translations vs. machine translation:** Slower but safer for ad copy. Machine translation in advertising is a legal risk — "naturally refreshing" could translate to something inappropriate in some markets.
- **Procedural mock images vs. placeholder text:** More code, but mock mode now tests the same pipeline path as real mode. The compositor doesn't know or care whether the hero came from DALL-E or from procedural generation.

---

## Key Principles (for future projects)

1. **Every stage's output is the next stage's input.** Test the contract between stages, not just the final result.
2. **Schema is the contract.** If a field exists in the model, it must be wired. If a constraint exists in the requirements, it must be validated.
3. **Silent fallbacks are lies.** If a feature has boundaries, surface them. Never return stale/wrong data without a warning.
4. **Validation must inspect the artifact.** Checking inputs is configuration validation. Checking outputs is quality assurance. They're different things.
5. **Mock mode is a real mode.** If mock output has different properties than real output, downstream tests are unreliable.
6. **Tests should prove claims, not prove execution.** If the README says "brand compliance," the tests should verify compliance results are accurate for known inputs.
