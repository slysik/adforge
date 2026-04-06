"""
LLM-powered campaign brief analyzer.

Uses GenAI as a JUDGMENT tool (not just an image generator) to:
  1. Score brief completeness and quality
  2. Identify missing or weak fields
  3. Suggest prompt enrichment for better hero generation
  4. Flag potential brand/legal risks before generation
  5. Generate creative direction recommendations

This demonstrates explainable AI orchestration — the LLM's analysis
is structured, auditable, and surfaced in the pipeline report.

In production, this would integrate with Adobe GenStudio or a
client's creative brief management system.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Optional

from rich.console import Console
from rich.panel import Panel

from .models import CampaignBrief

console = Console()


# ---------------------------------------------------------------------------
# Analysis result models
# ---------------------------------------------------------------------------

@dataclass
class BriefScore:
    """Structured quality score for a campaign brief."""
    overall: int = 0           # 0-100
    completeness: int = 0      # 0-25: are all fields filled meaningfully?
    clarity: int = 0           # 0-25: is the message clear and actionable?
    brand_strength: int = 0    # 0-25: are brand guidelines well-defined?
    targeting: int = 0         # 0-25: is the audience/region specific enough?


@dataclass
class BriefAnalysis:
    """Complete analysis of a campaign brief."""
    score: BriefScore
    strengths: list[str] = field(default_factory=list)
    weaknesses: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)
    risk_flags: list[str] = field(default_factory=list)
    prompt_enrichments: dict[str, str] = field(default_factory=dict)
    creative_direction: str = ""
    analyzed_by: str = "heuristic"  # "heuristic" or "llm"


# ---------------------------------------------------------------------------
# Heuristic analyzer (always available, no API key needed)
# ---------------------------------------------------------------------------

class HeuristicAnalyzer:
    """Rule-based brief analyzer — fast, deterministic, always available.

    This is the default analyzer. It applies structured heuristics to
    evaluate brief quality without any API calls. Every rule is explicit
    and auditable — important for interview defensibility.
    """

    def analyze(self, brief: CampaignBrief) -> BriefAnalysis:
        score = BriefScore()
        strengths = []
        weaknesses = []
        suggestions = []
        risk_flags = []
        enrichments = {}

        # ── Completeness (0-25) ──────────────────────────────────────
        completeness = 0
        if brief.message and len(brief.message) > 5:
            completeness += 5
        else:
            weaknesses.append("Campaign message is too short or generic")

        if brief.tagline:
            completeness += 3
            strengths.append("Tagline provided — adds messaging depth")
        else:
            suggestions.append("Add a tagline for secondary messaging on creatives")

        if len(brief.products) >= 2:
            completeness += 4
            strengths.append(f"{len(brief.products)} products defined")

        if len(brief.languages) > 1:
            completeness += 3
            strengths.append(f"Multi-language campaign ({', '.join(brief.languages)})")

        for p in brief.products:
            if p.keywords and len(p.keywords) >= 3:
                completeness += 2
            else:
                suggestions.append(f"Add more keywords for '{p.name}' — improves hero generation quality")

            if p.hero_image:
                strengths.append(f"Pre-existing hero for '{p.name}' — saves generation cost")
            else:
                enrichments[p.id] = self._enrich_prompt(p.name, p.description, p.keywords, brief)

        # Check product descriptions quality
        for p in brief.products:
            if len(p.description) < 20:
                weaknesses.append(f"Product '{p.name}' description is thin — may produce generic heroes")
            elif len(p.description) > 50:
                completeness += 2

        score.completeness = min(25, completeness)

        # ── Clarity (0-25) ───────────────────────────────────────────
        clarity = 0

        # Message actionability
        action_words = ["stay", "get", "try", "feel", "glow", "discover", "taste", "enjoy"]
        if any(w in brief.message.lower() for w in action_words):
            clarity += 8
            strengths.append("Campaign message uses action-oriented language")
        else:
            clarity += 3
            suggestions.append("Consider action-oriented messaging (e.g., 'Discover...', 'Feel...')")

        # Audience specificity
        if any(term in brief.target_audience.lower() for term in ["ages", "year", "gen z", "millennial", "women", "men"]):
            clarity += 8
            strengths.append("Target audience includes demographic specifics")
        else:
            clarity += 3
            weaknesses.append("Target audience is vague — add age range or psychographic details")

        # Region specificity
        specific_regions = ["north america", "europe", "asia", "us", "uk", "germany", "france", "japan"]
        if any(r in brief.target_region.lower() for r in specific_regions):
            clarity += 6
        else:
            clarity += 2
            suggestions.append("Be more specific about target region for localized creative style")

        score.clarity = min(25, clarity)

        # ── Brand Strength (0-25) ────────────────────────────────────
        brand = 0
        bg = brief.brand_guidelines

        if len(bg.primary_colors) >= 2:
            brand += 6
            strengths.append(f"Brand palette defined ({len(bg.primary_colors)} colors)")
        else:
            weaknesses.append("Minimal brand palette — creatives may lack visual consistency")

        if bg.accent_color:
            brand += 3
            strengths.append("Accent color specified for secondary UI elements")

        if bg.logo_path:
            brand += 5
            strengths.append("Logo asset provided")
        else:
            weaknesses.append("No logo provided — creatives will lack brand identity mark")

        if bg.prohibited_words:
            brand += 4
            strengths.append(f"Prohibited words list ({len(bg.prohibited_words)} terms)")

        if bg.required_disclaimer:
            brand += 4
            strengths.append("Legal disclaimer configured")
        else:
            risk_flags.append("No required disclaimer — verify legal compliance for target markets")

        if bg.font_family and bg.font_family.lower() != "arial":
            brand += 3
            strengths.append(f"Custom font family: {bg.font_family}")

        score.brand_strength = min(25, brand)

        # ── Targeting (0-25) ─────────────────────────────────────────
        targeting = 0

        if len(brief.languages) >= 2:
            targeting += 8
        elif len(brief.languages) == 1:
            targeting += 3

        if len(brief.aspect_ratios) >= 3:
            targeting += 8
            strengths.append(f"{len(brief.aspect_ratios)} aspect ratios for multi-platform delivery")

        # Check if ratios cover major platforms
        ratio_values = {r.ratio for r in brief.aspect_ratios}
        platform_coverage = {"1:1", "9:16", "16:9"}
        covered = ratio_values & platform_coverage
        if covered == platform_coverage:
            targeting += 6
            strengths.append("Full platform coverage: Instagram, Stories/Reels, Facebook/YouTube")
        else:
            missing = platform_coverage - covered
            suggestions.append(f"Missing aspect ratios: {', '.join(missing)}")

        score.targeting = min(25, targeting)

        # ── Overall ──────────────────────────────────────────────────
        score.overall = score.completeness + score.clarity + score.brand_strength + score.targeting

        # ── Risk flags ───────────────────────────────────────────────
        sensitive_terms = ["free", "best", "guaranteed", "miracle", "#1", "proven"]
        msg_lower = brief.message.lower()
        for term in sensitive_terms:
            if term in msg_lower:
                risk_flags.append(f"Campaign message contains '{term}' — may trigger ad platform review")

        # ── Creative direction ───────────────────────────────────────
        direction = self._infer_creative_direction(brief)

        return BriefAnalysis(
            score=score,
            strengths=strengths,
            weaknesses=weaknesses,
            suggestions=suggestions,
            risk_flags=risk_flags,
            prompt_enrichments=enrichments,
            creative_direction=direction,
            analyzed_by="heuristic",
        )

    def _enrich_prompt(
        self,
        product_name: str,
        description: str,
        keywords: list[str],
        brief: CampaignBrief,
    ) -> str:
        """Generate enriched prompt context for hero generation."""
        parts = []

        # Audience-informed style
        audience_lower = brief.target_audience.lower()
        if "millennial" in audience_lower or "gen z" in audience_lower:
            parts.append("modern, vibrant, social-media-ready aesthetic")
        elif "premium" in audience_lower or "luxury" in audience_lower:
            parts.append("premium, elegant, aspirational aesthetic")
        elif "professional" in audience_lower:
            parts.append("clean, corporate, trustworthy aesthetic")

        # Region-informed style
        region_lower = brief.target_region.lower()
        if "europe" in region_lower:
            parts.append("European design sensibility, sophisticated color palette")
        elif "asia" in region_lower or "japan" in region_lower:
            parts.append("clean composition, attention to white space and detail")
        elif "north america" in region_lower:
            parts.append("bold, energetic, lifestyle-oriented")

        # Keyword-informed elements
        if keywords:
            parts.append(f"featuring: {', '.join(keywords[:5])}")

        return "; ".join(parts) if parts else ""

    def _infer_creative_direction(self, brief: CampaignBrief) -> str:
        """Infer creative direction from brief signals."""
        signals = []

        msg_lower = brief.message.lower()
        if any(w in msg_lower for w in ["fresh", "natural", "organic", "clean"]):
            signals.append("nature-inspired")
        if any(w in msg_lower for w in ["glow", "luxury", "premium", "radiance"]):
            signals.append("premium/luxury")
        if any(w in msg_lower for w in ["summer", "winter", "holiday", "season"]):
            signals.append("seasonal")
        if any(w in msg_lower for w in ["new", "launch", "discover", "introducing"]):
            signals.append("product launch")

        if not signals:
            signals.append("general campaign")

        audience = brief.target_audience.lower()
        if "gen z" in audience:
            signals.append("youth-forward visual language")
        elif "25-45" in audience or "30-" in audience:
            signals.append("aspirational lifestyle")

        return f"Recommended direction: {', '.join(signals)}"


# ---------------------------------------------------------------------------
# LLM-powered analyzer (when API keys available)
# ---------------------------------------------------------------------------

class LLMAnalyzer:
    """LLM-enhanced brief analyzer.

    Augments the heuristic analysis with LLM-generated insights.
    Uses a structured prompt → structured JSON output pattern for
    reliable, parseable results.

    Falls back to heuristic analysis if the API call fails.
    """

    SYSTEM_PROMPT = """You are a senior creative strategist reviewing a campaign brief for a social media advertising campaign.

Analyze the brief and return a JSON object with:
{
  "strengths": ["list of what's strong about this brief"],
  "weaknesses": ["list of gaps or concerns"],
  "suggestions": ["actionable improvements"],
  "risk_flags": ["potential brand/legal/compliance risks"],
  "creative_direction": "2-3 sentence creative direction recommendation",
  "prompt_enrichments": {
    "product-id": "additional context to improve AI image generation for this product"
  }
}

Be specific and actionable. Focus on creative strategy, not technical implementation."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.heuristic = HeuristicAnalyzer()

    def analyze(self, brief: CampaignBrief) -> BriefAnalysis:
        """Analyze using both heuristic and LLM, merging results."""
        # Always run heuristic first (fast, deterministic)
        base = self.heuristic.analyze(brief)

        if not self.api_key:
            return base

        try:
            llm_insights = self._call_llm(brief)
            return self._merge(base, llm_insights)
        except Exception as exc:
            console.print(f"  [yellow]⚠ LLM analysis failed ({exc}), using heuristic only[/yellow]")
            return base

    def _call_llm(self, brief: CampaignBrief) -> dict:
        """Call the LLM with the brief for structured analysis."""
        from openai import OpenAI
        client = OpenAI(api_key=self.api_key)

        brief_text = self._format_brief_for_llm(brief)

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze this campaign brief:\n\n{brief_text}"},
            ],
            temperature=0.3,
            max_tokens=1000,
        )

        return json.loads(response.choices[0].message.content)

    def _format_brief_for_llm(self, brief: CampaignBrief) -> str:
        """Format brief as readable text for LLM analysis."""
        lines = [
            f"Campaign: {brief.name}",
            f"Brand: {brief.brand}",
            f"Message: {brief.message}",
            f"Tagline: {brief.tagline or '(none)'}",
            f"Region: {brief.target_region}",
            f"Audience: {brief.target_audience}",
            f"Languages: {', '.join(brief.languages)}",
            f"Colors: {', '.join(brief.brand_guidelines.primary_colors)}",
            f"Prohibited: {', '.join(brief.brand_guidelines.prohibited_words) or '(none)'}",
            "",
            "Products:",
        ]
        for p in brief.products:
            lines.append(f"  - {p.name}: {p.description}")
            lines.append(f"    Keywords: {', '.join(p.keywords)}")
            lines.append(f"    Hero: {'existing' if p.hero_image else 'needs generation'}")

        return "\n".join(lines)

    def _merge(self, base: BriefAnalysis, llm: dict) -> BriefAnalysis:
        """Merge LLM insights into heuristic analysis."""
        base.analyzed_by = "heuristic+llm"

        # Add LLM insights that aren't already present
        for s in llm.get("strengths", []):
            if s not in base.strengths:
                base.strengths.append(f"[AI] {s}")

        for w in llm.get("weaknesses", []):
            if w not in base.weaknesses:
                base.weaknesses.append(f"[AI] {w}")

        for s in llm.get("suggestions", []):
            if s not in base.suggestions:
                base.suggestions.append(f"[AI] {s}")

        for r in llm.get("risk_flags", []):
            if r not in base.risk_flags:
                base.risk_flags.append(f"[AI] {r}")

        if llm.get("creative_direction"):
            base.creative_direction = f"{base.creative_direction}\n[AI] {llm['creative_direction']}"

        for pid, enrichment in llm.get("prompt_enrichments", {}).items():
            existing = base.prompt_enrichments.get(pid, "")
            base.prompt_enrichments[pid] = f"{existing}; [AI] {enrichment}" if existing else f"[AI] {enrichment}"

        return base


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def analyze_brief(brief: CampaignBrief, use_llm: bool = False, api_key: Optional[str] = None) -> BriefAnalysis:
    """Analyze a campaign brief and return structured insights.

    Args:
        brief: The campaign brief to analyze
        use_llm: Whether to augment heuristic analysis with LLM insights
        api_key: OpenAI API key (optional, falls back to env)

    Returns:
        BriefAnalysis with scores, strengths, weaknesses, and recommendations
    """
    if use_llm:
        return LLMAnalyzer(api_key=api_key).analyze(brief)
    return HeuristicAnalyzer().analyze(brief)


def print_analysis(analysis: BriefAnalysis) -> None:
    """Print a formatted brief analysis to console."""
    score = analysis.score

    # Score bar
    bar_filled = "█" * (score.overall // 5)
    bar_empty = "░" * (20 - score.overall // 5)
    grade = "A" if score.overall >= 80 else "B" if score.overall >= 60 else "C" if score.overall >= 40 else "D"

    console.print(Panel.fit(
        f"[bold]Brief Quality Score: {score.overall}/100 ({grade})[/bold]\n"
        f"  [{bar_filled}{bar_empty}]\n\n"
        f"  Completeness:   {score.completeness}/25\n"
        f"  Clarity:        {score.clarity}/25\n"
        f"  Brand Strength: {score.brand_strength}/25\n"
        f"  Targeting:      {score.targeting}/25\n\n"
        f"  Analyzed by: {analysis.analyzed_by}",
        title="[cyan]Brief Analysis[/cyan]",
        border_style="cyan",
    ))

    if analysis.strengths:
        console.print("\n[green]✓ Strengths:[/green]")
        for s in analysis.strengths:
            console.print(f"  • {s}")

    if analysis.weaknesses:
        console.print("\n[yellow]⚠ Weaknesses:[/yellow]")
        for w in analysis.weaknesses:
            console.print(f"  • {w}")

    if analysis.suggestions:
        console.print("\n[blue]💡 Suggestions:[/blue]")
        for s in analysis.suggestions:
            console.print(f"  • {s}")

    if analysis.risk_flags:
        console.print("\n[red]🚩 Risk Flags:[/red]")
        for r in analysis.risk_flags:
            console.print(f"  • {r}")

    if analysis.creative_direction:
        console.print(f"\n[bold]🎨 Creative Direction:[/bold] {analysis.creative_direction}")

    console.print()
