# AdForge Demo Script (~2–3 minutes)

## Part 1: Install from Scratch

**Prerequisites:** [just](https://github.com/casey/just#installation) + Python 3.9+

```bash
git clone https://github.com/slysik/adforge.git && cd adforge
just install
just start-app
```

Browser opens to `http://localhost:8501`. You should see the AdForge hero banner and the **Brief Builder** expander (open by default).

---

## Part 2: Build a Brief (4 tabs)

### Tab 1 — Enter Campaign Info

Fields are pre-filled with Blue Beach House Designs defaults:

- Campaign Name: `My Campaign 2025`
- Brand Name: `Blue Beach House Designs`
- Target Region: `Southern Florida — Naples & Palm Beach`
- Target Audience: `Home decor designers, interior stylists, ages 30-60`
- Campaign Message: `Handcrafted coastal elegance for your home`
- Languages: `EN`

> **Demo tip:** Change the Campaign Name or Message to show it's editable, then move on.

### Tab 2 — Brand Guidelines

- Primary Color, Secondary Color, Accent Color (pre-filled)
- Font choices
- Logo path

> **Demo tip:** Click the tab to show the form. No changes needed — defaults work.

### Tab 3 — Products

- 3 products pre-loaded (Resort Shell Handbag, Cowrie Shell Box, Painted Shell Art)
- Each with keywords and hero image path

> **Demo tip:** Click the tab to briefly show products are configured, then move to Review.

### Tab 4 — Review

Shows a summary card with all brief details:

- Brand, Campaign, Message, Region, Audience, Products count
- "Ready to generate **9 creatives** (3 aspect ratios × 3 products × 1 language(s))."
- **Image Provider:** `mock` (no API key needed)
- **Layout Template:** `auto`

---

## Part 3: Run Pipeline

1. On the **Review** tab, click **🚀 Run Pipeline**
2. Watch the stepper animate through 7 stages: Brief Ingestion → Analysis → Asset Resolution → Hero Generation → Layout Rendering → Policy Checks → Reporting
3. **Pipeline Complete!** appears alongside the stepper (same row)
4. The **Brief Builder** auto-collapses
5. **4. Results** section appears with 6 tabs

---

## Part 4: Walk Through Result Tabs

### 📋 Campaign (default tab)

- Metric cards: Total, Created, Hero Reused, Failed, Time, Saved
- Pipeline Overview stepper (all green checkmarks)
- Brief Analysis score and quality breakdown
- Product list with details

### 🖼️ Gallery

- Grid of all 9 generated creatives
- Each shows product name, aspect ratio, and language
- Click any image to see full-size preview

### ✅ Approval Queue

- Simulated approval workflow
- Each creative shows Approve/Reject controls
- Status badges (Pending, Approved, Rejected)

### 🔀 A/B Compare

- Side-by-side template comparison
- Shows how the same product looks in different layout templates
- Helps pick the best visual treatment per product

### 📈 Performance

- Campaign performance charts (sample data)
- CTR, impressions, engagement metrics
- Bar/line charts showing projected performance across creatives

### 📊 Metrics

- Per-creative KPI table
- Detailed breakdown: dimensions, file size, compliance score
- Export-ready data view

---

## Wrap-Up

> "From `git clone` to 9 campaign-ready creatives in under 60 seconds — no API keys required. Swap `mock` for `gemini` and you get real AI-generated hero images from Google Imagen 4.0."
