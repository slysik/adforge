"""
Reporting module.

Generates:
  - Console summary (via Rich)
  - JSON report file (with metrics + analysis)
  - HTML visual dashboard with thumbnails, metrics, and brief analysis
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from jinja2 import Template
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from .models import PipelineResult, GeneratedAsset, AssetStatus, ComplianceStatus

console = Console()

# ---------------------------------------------------------------------------
# Status → display helpers
# ---------------------------------------------------------------------------

_COMPLIANCE_ICONS = {
    ComplianceStatus.PASSED: "[green]✓[/green]",
    ComplianceStatus.WARNING: "[yellow]⚠[/yellow]",
    ComplianceStatus.FAILED: "[red]✗[/red]",
    ComplianceStatus.NOT_CHECKED: "[dim]–[/dim]",
}

_COMPLIANCE_CSS = {
    "passed": "pass",
    "warning": "warn",
    "failed": "failed",
    "not_checked": "na",
}

_COMPLIANCE_SYMBOL = {
    "passed": "✓",
    "warning": "⚠",
    "failed": "✗",
    "not_checked": "–",
}

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AdForge Report – {{ result.campaign_name }}</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
               background: #0a0a0f; color: #e0e0e0; padding: 2rem; }

        /* Header */
        .header { display: flex; align-items: center; gap: 1rem; margin-bottom: 0.5rem; }
        .header svg { width: 40px; height: 40px; }
        h1 { font-size: 2rem; color: #fff; }
        .subtitle { color: #888; margin-bottom: 2rem; font-size: 0.9rem; }

        /* Nav tabs */
        .tabs { display: flex; gap: 0; margin-bottom: 2rem; border-bottom: 2px solid #222; }
        .tab { padding: 0.8rem 1.5rem; color: #888; cursor: pointer; border-bottom: 2px solid transparent;
               margin-bottom: -2px; transition: all 0.2s; font-size: 0.9rem; }
        .tab:hover { color: #fff; }
        .tab.active { color: #4fc3f7; border-bottom-color: #4fc3f7; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }

        /* Stats bar */
        .stats { display: flex; gap: 1.2rem; margin-bottom: 2rem; flex-wrap: wrap; }
        .stat { background: #12121e; padding: 1.2rem 1.6rem; border-radius: 12px;
                border: 1px solid #1e1e35; min-width: 140px; flex: 1; }
        .stat .num { font-size: 2rem; font-weight: 700; color: #4fc3f7; }
        .stat .label { font-size: 0.8rem; color: #666; margin-top: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
        .stat.green .num { color: #66bb6a; }
        .stat.blue .num { color: #42a5f5; }
        .stat.orange .num { color: #ffa726; }
        .stat.red .num { color: #ef5350; }
        .stat.purple .num { color: #ab47bc; }

        /* Brief analysis */
        .analysis-grid { display: grid; grid-template-columns: 300px 1fr; gap: 2rem; margin-bottom: 2rem; }
        .score-ring { text-align: center; padding: 2rem; background: #12121e; border-radius: 16px; border: 1px solid #1e1e35; }
        .score-number { font-size: 4rem; font-weight: 800; color: #4fc3f7; }
        .score-label { color: #888; font-size: 0.85rem; margin-top: 4px; }
        .score-bars { padding: 1.5rem 0; }
        .score-bar { margin-bottom: 1rem; }
        .score-bar-label { display: flex; justify-content: space-between; font-size: 0.8rem; margin-bottom: 4px; }
        .score-bar-track { height: 8px; background: #1a1a2e; border-radius: 4px; overflow: hidden; }
        .score-bar-fill { height: 100%; border-radius: 4px; transition: width 0.3s; }
        .insights { background: #12121e; border-radius: 16px; border: 1px solid #1e1e35; padding: 1.5rem; }
        .insight-section { margin-bottom: 1.2rem; }
        .insight-section h3 { font-size: 0.85rem; color: #888; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 0.5rem; }
        .insight-section ul { list-style: none; padding: 0; }
        .insight-section li { padding: 4px 0; font-size: 0.85rem; color: #ccc; }
        .insight-section li::before { content: "•"; margin-right: 8px; }
        .insight-section.strengths li::before { content: "✓"; color: #66bb6a; }
        .insight-section.weaknesses li::before { content: "⚠"; color: #ffa726; }
        .insight-section.risks li::before { content: "🚩"; }
        .insight-section.suggestions li::before { content: "💡"; }

        /* Metrics table */
        .metrics-table { width: 100%; border-collapse: collapse; margin-bottom: 2rem; background: #12121e;
                         border-radius: 12px; overflow: hidden; }
        .metrics-table th { background: #1a1a2e; padding: 1rem; text-align: left; font-size: 0.8rem;
                            color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
        .metrics-table td { padding: 0.8rem 1rem; border-top: 1px solid #1a1a2e; font-size: 0.85rem; }
        .metrics-table tr:hover td { background: #161628; }

        /* Asset grid */
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
                gap: 1.5rem; margin-top: 1rem; }
        .card { background: #12121e; border-radius: 12px; overflow: hidden;
                border: 1px solid #1e1e35; transition: all 0.2s; }
        .card:hover { transform: translateY(-2px); border-color: #4fc3f7; box-shadow: 0 8px 30px rgba(79,195,247,0.1); }
        .card img { width: 100%; height: 220px; object-fit: cover; }
        .card-body { padding: 1rem; }
        .card-body h3 { font-size: 0.95rem; margin-bottom: 0.4rem; color: #fff; }
        .card-body .meta { font-size: 0.8rem; color: #888; }
        .badge { display: inline-block; padding: 2px 10px; border-radius: 20px;
                 font-size: 0.72rem; font-weight: 600; margin-right: 4px; }
        .badge.generated { background: #1b5e20; color: #a5d6a7; }
        .badge.reused { background: #0d47a1; color: #90caf9; }
        .badge.failed { background: #b71c1c; color: #ef9a9a; }
        .badge.pass { background: #1b5e20; color: #a5d6a7; }
        .badge.warn { background: #e65100; color: #ffcc80; }
        .badge.na { background: #222; color: #666; }
        .notes { font-size: 0.75rem; color: #888; margin-top: 6px; line-height: 1.4; }

        /* Warnings */
        .warnings { background: #1a1500; border: 1px solid #332a00; border-radius: 12px;
                     padding: 1rem; margin-bottom: 2rem; }
        .warnings li { color: #ffcc80; font-size: 0.85rem; padding: 2px 0; }

        /* Pipeline flow */
        .pipeline-flow { display: flex; gap: 0; margin-bottom: 2rem; overflow-x: auto; padding: 1rem 0; }
        .pipeline-step { flex: 1; min-width: 140px; text-align: center; padding: 1rem; position: relative; }
        .pipeline-step::after { content: "→"; position: absolute; right: -8px; top: 50%; transform: translateY(-50%);
                                 color: #333; font-size: 1.2rem; }
        .pipeline-step:last-child::after { content: ""; }
        .pipeline-step .step-icon { font-size: 1.5rem; margin-bottom: 0.3rem; }
        .pipeline-step .step-label { font-size: 0.75rem; color: #888; text-transform: uppercase; letter-spacing: 0.5px; }
        .pipeline-step .step-time { font-size: 0.8rem; color: #4fc3f7; margin-top: 0.2rem; }

        /* Provider badge */
        .provider-badge { display: inline-flex; align-items: center; gap: 0.5rem; padding: 0.4rem 1rem;
                          background: #1a1a2e; border: 1px solid #333; border-radius: 8px; margin-bottom: 1rem; }
        .provider-badge.firefly { border-color: #e03e2d; }
        .provider-badge.dalle { border-color: #10a37f; }
        .provider-badge.mock { border-color: #666; }

        /* Footer */
        .footer { margin-top: 3rem; text-align: center; color: #444; font-size: 0.75rem; }
        .footer a { color: #4fc3f7; text-decoration: none; }

        /* Filter bar */
        .filter-bar { display: flex; gap: 0.5rem; margin-bottom: 1rem; flex-wrap: wrap; }
        .filter-btn { padding: 0.4rem 1rem; background: #1a1a2e; border: 1px solid #333; border-radius: 20px;
                      color: #888; cursor: pointer; font-size: 0.8rem; transition: all 0.2s; }
        .filter-btn:hover, .filter-btn.active { background: #4fc3f7; color: #000; border-color: #4fc3f7; }
    </style>
</head>
<body>
    <div class="header">
        <svg viewBox="0 0 40 40" fill="none" xmlns="http://www.w3.org/2000/svg">
            <rect width="40" height="40" rx="8" fill="#4fc3f7" fill-opacity="0.1"/>
            <path d="M12 28L20 12L28 28H12Z" stroke="#4fc3f7" stroke-width="2" fill="none"/>
            <circle cx="20" cy="22" r="3" fill="#4fc3f7"/>
        </svg>
        <h1>AdForge</h1>
    </div>
    <p class="subtitle">{{ result.campaign_name }} — Generated {{ timestamp }} — Provider: {{ provider_name }}</p>

    <!-- Tabs -->
    <div class="tabs">
        <div class="tab active" onclick="showTab('overview')">Overview</div>
        <div class="tab" onclick="showTab('assets')">Assets ({{ result.total_assets }})</div>
        {% if analysis %}<div class="tab" onclick="showTab('analysis')">Brief Analysis</div>{% endif %}
        {% if metrics %}<div class="tab" onclick="showTab('performance')">Performance</div>{% endif %}
        <div class="tab" onclick="showTab('architecture')">Architecture</div>
    </div>

    <!-- Overview Tab -->
    <div id="tab-overview" class="tab-content active">
        <div class="stats">
            <div class="stat"><div class="num">{{ result.total_assets }}</div><div class="label">Total Assets</div></div>
            <div class="stat green"><div class="num">{{ result.created_count }}</div><div class="label">Created</div></div>
            <div class="stat blue"><div class="num">{{ result.hero_reused_count }}</div><div class="label">Hero Reused</div></div>
            <div class="stat red"><div class="num">{{ result.failed_count }}</div><div class="label">Failed</div></div>
            <div class="stat purple"><div class="num">{{ "%.1f"|format(result.elapsed_seconds) }}s</div><div class="label">Elapsed</div></div>
            {% if metrics %}
            <div class="stat orange"><div class="num">${{ "%.3f"|format(metrics.total_estimated_cost_usd) }}</div><div class="label">Est. Cost</div></div>
            {% endif %}
        </div>

        {% if metrics and metrics.stages %}
        <!-- Pipeline Flow -->
        <div class="pipeline-flow">
            {% for stage in metrics.stages %}
            <div class="pipeline-step">
                <div class="step-icon">{% if 'brief' in stage.name %}📋{% elif 'analysis' in stage.name %}🔍{% elif 'gen' in stage.name %}🎨{% elif 'compose' in stage.name %}🖼️{% elif 'valid' in stage.name %}✅{% else %}⚙️{% endif %}</div>
                <div class="step-label">{{ stage.name.replace('_', ' ') }}</div>
                <div class="step-time">{{ stage.elapsed_ms }}ms</div>
            </div>
            {% endfor %}
        </div>
        {% endif %}

        {% if result.warnings %}
        <div class="warnings">
            <strong>⚠ Warnings:</strong>
            <ul style="margin-top:0.5rem;padding-left:1.5rem;">
            {% for w in result.warnings %}
                <li>{{ w }}</li>
            {% endfor %}
            </ul>
        </div>
        {% endif %}

        <!-- Quick preview grid (first 6) -->
        <h2 style="margin-bottom:1rem; font-size: 1.1rem;">Recent Assets</h2>
        <div class="grid">
        {% for asset in result.assets[:6] %}
            <div class="card">
                {% if asset.file_path and file_exists(asset.file_path) %}
                <img src="file://{{ abs_path(asset.file_path) }}" alt="{{ asset.product_id }}">
                {% else %}
                <div style="height:220px;background:#111;display:flex;align-items:center;justify-content:center;color:#333;">No preview</div>
                {% endif %}
                <div class="card-body">
                    <h3>{{ asset.product_id }} — {{ asset.aspect_ratio }}</h3>
                    <div class="meta">
                        <span class="badge {{ asset.hero_status.value }}">Hero: {{ asset.hero_status.value }}</span>
                        <span class="badge {{ compliance_css(asset.brand_compliance.status.value) }}">
                            Brand: {{ compliance_sym(asset.brand_compliance.status.value) }}
                        </span>
                        <span class="badge {{ compliance_css(asset.legal_compliance.status.value) }}">
                            Legal: {{ compliance_sym(asset.legal_compliance.status.value) }}
                        </span>
                        <span style="color:#666;font-size:0.7rem;">{{ asset.language }}</span>
                    </div>
                </div>
            </div>
        {% endfor %}
        </div>
    </div>

    <!-- Assets Tab -->
    <div id="tab-assets" class="tab-content">
        <div class="filter-bar">
            <div class="filter-btn active" onclick="filterAssets('all', this)">All</div>
            {% for pid in product_ids %}
            <div class="filter-btn" onclick="filterAssets('{{ pid }}', this)">{{ pid }}</div>
            {% endfor %}
        </div>
        <div class="grid" id="assets-grid">
        {% for asset in result.assets %}
            <div class="card asset-card" data-product="{{ asset.product_id }}" data-ratio="{{ asset.aspect_ratio }}" data-lang="{{ asset.language }}">
                {% if asset.file_path and file_exists(asset.file_path) %}
                <img src="file://{{ abs_path(asset.file_path) }}" alt="{{ asset.product_id }}">
                {% else %}
                <div style="height:220px;background:#111;display:flex;align-items:center;justify-content:center;color:#333;">No preview</div>
                {% endif %}
                <div class="card-body">
                    <h3>{{ asset.product_id }} — {{ asset.aspect_ratio }}</h3>
                    <div class="meta">
                        <span class="badge {{ asset.hero_status.value }}">Hero: {{ asset.hero_status.value }}</span>
                        <span class="badge {{ asset.status.value }}">{{ asset.status.value }}</span>
                        <span class="badge {{ compliance_css(asset.brand_compliance.status.value) }}">
                            Brand: {{ compliance_sym(asset.brand_compliance.status.value) }}
                        </span>
                        <span class="badge {{ compliance_css(asset.legal_compliance.status.value) }}">
                            Legal: {{ compliance_sym(asset.legal_compliance.status.value) }}
                        </span>
                    </div>
                    <div class="meta" style="margin-top:4px;">Language: {{ asset.language }}</div>
                    {% if asset.brand_compliance.notes %}
                    <div class="notes">{{ asset.brand_compliance.notes | join('; ') }}</div>
                    {% endif %}
                    {% if asset.prompt_used %}
                    <div class="notes" style="margin-top:4px;"><em>Prompt: {{ asset.prompt_used[:120] }}…</em></div>
                    {% endif %}
                </div>
            </div>
        {% endfor %}
        </div>
    </div>

    {% if analysis %}
    <!-- Analysis Tab -->
    <div id="tab-analysis" class="tab-content">
        <div class="analysis-grid">
            <div class="score-ring">
                <div class="score-number">{{ analysis.score.overall }}</div>
                <div class="score-label">Brief Quality Score / 100</div>
                <div class="score-bars" style="margin-top: 1.5rem;">
                    <div class="score-bar">
                        <div class="score-bar-label"><span>Completeness</span><span>{{ analysis.score.completeness }}/25</span></div>
                        <div class="score-bar-track"><div class="score-bar-fill" style="width:{{ (analysis.score.completeness / 25 * 100)|int }}%;background:#66bb6a;"></div></div>
                    </div>
                    <div class="score-bar">
                        <div class="score-bar-label"><span>Clarity</span><span>{{ analysis.score.clarity }}/25</span></div>
                        <div class="score-bar-track"><div class="score-bar-fill" style="width:{{ (analysis.score.clarity / 25 * 100)|int }}%;background:#42a5f5;"></div></div>
                    </div>
                    <div class="score-bar">
                        <div class="score-bar-label"><span>Brand Strength</span><span>{{ analysis.score.brand_strength }}/25</span></div>
                        <div class="score-bar-track"><div class="score-bar-fill" style="width:{{ (analysis.score.brand_strength / 25 * 100)|int }}%;background:#ab47bc;"></div></div>
                    </div>
                    <div class="score-bar">
                        <div class="score-bar-label"><span>Targeting</span><span>{{ analysis.score.targeting }}/25</span></div>
                        <div class="score-bar-track"><div class="score-bar-fill" style="width:{{ (analysis.score.targeting / 25 * 100)|int }}%;background:#ffa726;"></div></div>
                    </div>
                </div>
                <div style="margin-top:1rem;font-size:0.75rem;color:#666;">Analyzed by: {{ analysis.analyzed_by }}</div>
            </div>
            <div class="insights">
                {% if analysis.creative_direction %}
                <div class="insight-section">
                    <h3>🎨 Creative Direction</h3>
                    <p style="font-size:0.9rem;color:#ddd;">{{ analysis.creative_direction }}</p>
                </div>
                {% endif %}
                {% if analysis.strengths %}
                <div class="insight-section strengths">
                    <h3>Strengths</h3>
                    <ul>{% for s in analysis.strengths %}<li>{{ s }}</li>{% endfor %}</ul>
                </div>
                {% endif %}
                {% if analysis.weaknesses %}
                <div class="insight-section weaknesses">
                    <h3>Weaknesses</h3>
                    <ul>{% for w in analysis.weaknesses %}<li>{{ w }}</li>{% endfor %}</ul>
                </div>
                {% endif %}
                {% if analysis.suggestions %}
                <div class="insight-section suggestions">
                    <h3>Suggestions</h3>
                    <ul>{% for s in analysis.suggestions %}<li>{{ s }}</li>{% endfor %}</ul>
                </div>
                {% endif %}
                {% if analysis.risk_flags %}
                <div class="insight-section risks">
                    <h3>Risk Flags</h3>
                    <ul>{% for r in analysis.risk_flags %}<li>{{ r }}</li>{% endfor %}</ul>
                </div>
                {% endif %}
            </div>
        </div>
    </div>
    {% endif %}

    {% if metrics %}
    <!-- Performance Tab -->
    <div id="tab-performance" class="tab-content">
        <div class="stats">
            <div class="stat"><div class="num">{{ metrics.total_elapsed_ms }}ms</div><div class="label">Total Time</div></div>
            <div class="stat blue"><div class="num">{{ metrics.total_api_calls }}</div><div class="label">API Calls</div></div>
            <div class="stat orange"><div class="num">${{ "%.3f"|format(metrics.total_estimated_cost_usd) }}</div><div class="label">Est. Cost</div></div>
            <div class="stat purple"><div class="num">{{ metrics.provider_used }}</div><div class="label">Provider</div></div>
        </div>

        <h3 style="margin-bottom:1rem;">Stage Breakdown</h3>
        <table class="metrics-table">
            <thead><tr><th>Stage</th><th>Time</th><th>Items</th><th>API Calls</th><th>Est. Cost</th><th>Notes</th></tr></thead>
            <tbody>
            {% for stage in metrics.stages %}
            <tr>
                <td>{{ stage.name }}</td>
                <td style="color:#4fc3f7;">{{ stage.elapsed_ms }}ms</td>
                <td>{{ stage.items_processed }}</td>
                <td>{{ stage.api_calls }}</td>
                <td style="color:#ffa726;">{% if stage.estimated_cost_usd > 0 %}${{ "%.3f"|format(stage.estimated_cost_usd) }}{% else %}–{% endif %}</td>
                <td style="color:#888;font-size:0.8rem;">{{ stage.notes|join(', ') }}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>

        {% if metrics.per_asset %}
        <h3 style="margin-bottom:1rem;">Per-Asset Metrics</h3>
        <table class="metrics-table">
            <thead><tr><th>Product</th><th>Ratio</th><th>Lang</th><th>Provider</th><th>Gen (ms)</th><th>Compose (ms)</th><th>Validate (ms)</th><th>Cost</th></tr></thead>
            <tbody>
            {% for a in metrics.per_asset %}
            <tr>
                <td>{{ a.product_id }}</td>
                <td>{{ a.aspect_ratio }}</td>
                <td>{{ a.language }}</td>
                <td>{{ a.provider }}</td>
                <td style="color:#4fc3f7;">{{ a.generation_ms }}</td>
                <td>{{ a.composition_ms }}</td>
                <td>{{ a.validation_ms }}</td>
                <td style="color:#ffa726;">{% if a.estimated_cost_usd > 0 %}${{ "%.3f"|format(a.estimated_cost_usd) }}{% else %}–{% endif %}</td>
            </tr>
            {% endfor %}
            </tbody>
        </table>
        {% endif %}
    </div>
    {% endif %}

    <!-- Architecture Tab -->
    <div id="tab-architecture" class="tab-content">
        <div style="background:#12121e;border-radius:16px;border:1px solid #1e1e35;padding:2rem;">
            <h2 style="margin-bottom:1rem;">Pipeline Architecture</h2>
            <pre style="font-family:monospace;font-size:0.8rem;color:#ccc;line-height:1.6;">
┌─────────────────────────────────────────────────────────────────────────────┐
│                            CLI / API Layer                                  │
│                         click + REST-ready                                  │
└─────────────────────┬───────────────────────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────────────────────┐
│                         Pipeline Orchestrator                               │
│              Stages: Ingest → Analyze → Resolve → Generate →                │
│                      Compose → Validate → Report                            │
└──┬────────┬─────────┬──────────┬──────────┬──────────┬──────────┬───────────┘
   │        │         │          │          │          │          │
   ▼        ▼         ▼          ▼          ▼          ▼          ▼
┌──────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐
│Brief │ │Brief   │ │Provider│ │Template│ │Compos- │ │Valida- │ │Report  │
│Models│ │Analyzer│ │Layer   │ │System  │ │itor   │ │tor     │ │Engine  │
│      │ │        │ │        │ │        │ │        │ │        │ │        │
│Pydant│ │Heurist │ │Firefly │ │Product │ │Resize  │ │Brand   │ │Console │
│ic    │ │ic +    │ │DALL-E  │ │Editor- │ │Overlay │ │Legal   │ │JSON    │
│valid-│ │LLM     │ │Mock    │ │ial     │ │Text    │ │Pixel   │ │HTML    │
│ation │ │scoring │ │        │ │Split   │ │Logo    │ │verify  │ │Metrics │
└──────┘ └────────┘ │Auto-   │ │Minimal │ └────────┘ └────────┘ └────────┘
                    │resolve │ │Bold    │
                    └────────┘ └────────┘
                         │
              ┌──────────┼──────────┐
              ▼          ▼          ▼
         ┌────────┐ ┌────────┐ ┌────────┐
         │Adobe   │ │OpenAI  │ │Mock    │
         │Firefly │ │DALL-E 3│ │(test)  │
         │Services│ │        │ │        │
         │        │ │$0.04/  │ │$0.00   │
         │$0.04/  │ │image   │ │        │
         │image   │ └────────┘ └────────┘
         │        │
         │Generate│
         │Expand  │
         │Fill    │
         └────────┘
            </pre>
            <div style="margin-top:2rem;">
                <h3 style="margin-bottom:0.5rem;">Production Extension Points</h3>
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;font-size:0.85rem;">
                    <div style="padding:1rem;background:#0a0a0f;border-radius:8px;border:1px solid #1e1e35;">
                        <strong style="color:#4fc3f7;">Adobe Integration</strong>
                        <ul style="margin-top:0.5rem;padding-left:1rem;color:#aaa;">
                            <li>Firefly Services for generation + expand + fill</li>
                            <li>AEM DAM for asset storage + retrieval</li>
                            <li>GenStudio for brief management</li>
                            <li>Creative Cloud Libraries for brand assets</li>
                            <li>Photoshop API for advanced compositing</li>
                        </ul>
                    </div>
                    <div style="padding:1rem;background:#0a0a0f;border-radius:8px;border:1px solid #1e1e35;">
                        <strong style="color:#4fc3f7;">Cloud & Scale</strong>
                        <ul style="margin-top:0.5rem;padding-left:1rem;color:#aaa;">
                            <li>S3/Azure Blob for asset storage</li>
                            <li>CDN delivery for published creatives</li>
                            <li>Webhook events for pipeline stages</li>
                            <li>Async job queue for batch campaigns</li>
                            <li>Cost tracking per client/campaign</li>
                        </ul>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        AdForge — Creative Automation Pipeline — <a href="#">Documentation</a>
    </div>

    <script>
    function showTab(name) {
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        document.getElementById('tab-' + name).classList.add('active');
        event.target.classList.add('active');
    }
    function filterAssets(product, btn) {
        document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        document.querySelectorAll('.asset-card').forEach(card => {
            if (product === 'all' || card.dataset.product === product) {
                card.style.display = '';
            } else {
                card.style.display = 'none';
            }
        });
    }
    </script>
</body>
</html>
"""


def print_console_report(result: PipelineResult) -> None:
    """Print a rich summary table to the console."""
    console.print()
    console.print(Panel.fit(
        f"[bold white]{result.campaign_name}[/bold white]\n"
        f"Total: {result.total_assets} | "
        f"[green]Created: {result.created_count}[/green] | "
        f"[blue]Hero Reused: {result.hero_reused_count}[/blue] | "
        f"[red]Failed: {result.failed_count}[/red] | "
        f"Time: {result.elapsed_seconds:.1f}s",
        title="AdForge Summary",
        border_style="cyan",
    ))

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Product", style="white")
    table.add_column("Ratio", style="white")
    table.add_column("Lang", style="white")
    table.add_column("Hero", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Brand", justify="center")
    table.add_column("Legal", justify="center")
    table.add_column("File", style="dim")

    hero_icons = {
        "reused": "[blue]♻[/blue]",
        "generated": "[green]✦[/green]",
        "failed": "[red]✗[/red]",
    }
    status_icons = {
        "reused": "[blue]♻[/blue]",
        "generated": "[green]✓[/green]",
        "failed": "[red]✗[/red]",
    }

    for a in result.assets:
        hero_icon = hero_icons.get(a.hero_status.value, "?")
        status_icon = status_icons.get(a.status.value, "?")
        brand_icon = _COMPLIANCE_ICONS.get(a.brand_compliance.status, "[dim]?[/dim]")
        legal_icon = _COMPLIANCE_ICONS.get(a.legal_compliance.status, "[dim]?[/dim]")
        table.add_row(
            a.product_id, a.aspect_ratio, a.language,
            hero_icon, status_icon, brand_icon, legal_icon,
            a.file_path,
        )

    console.print(table)

    for w in result.warnings:
        console.print(f"  [yellow]⚠ {w}[/yellow]")
    console.print()


def save_json_report(
    result: PipelineResult,
    output_dir: Path,
    metrics=None,
    analysis=None,
) -> Path:
    """Save pipeline results as JSON with optional metrics and analysis."""
    data = json.loads(result.model_dump_json(indent=2))

    if metrics:
        data["metrics"] = metrics.to_dict()

    if analysis:
        data["brief_analysis"] = {
            "score": {
                "overall": analysis.score.overall,
                "completeness": analysis.score.completeness,
                "clarity": analysis.score.clarity,
                "brand_strength": analysis.score.brand_strength,
                "targeting": analysis.score.targeting,
            },
            "strengths": analysis.strengths,
            "weaknesses": analysis.weaknesses,
            "suggestions": analysis.suggestions,
            "risk_flags": analysis.risk_flags,
            "creative_direction": analysis.creative_direction,
            "analyzed_by": analysis.analyzed_by,
        }

    path = output_dir / "report.json"
    path.write_text(json.dumps(data, indent=2))
    console.print(f"  [dim]JSON report: {path}[/dim]")
    return path


def save_html_report(
    result: PipelineResult,
    output_dir: Path,
    metrics=None,
    analysis=None,
) -> Path:
    """Render and save an HTML dashboard report."""
    template = Template(HTML_TEMPLATE)

    # Get unique product IDs for filter buttons
    product_ids = sorted(set(a.product_id for a in result.assets))

    # Build metrics dict for template
    metrics_dict = None
    if metrics:
        metrics_dict = metrics.to_dict()

    # Build analysis dict for template
    analysis_dict = None
    if analysis:
        analysis_dict = {
            "score": {
                "overall": analysis.score.overall,
                "completeness": analysis.score.completeness,
                "clarity": analysis.score.clarity,
                "brand_strength": analysis.score.brand_strength,
                "targeting": analysis.score.targeting,
            },
            "strengths": analysis.strengths,
            "weaknesses": analysis.weaknesses,
            "suggestions": analysis.suggestions,
            "risk_flags": analysis.risk_flags,
            "creative_direction": analysis.creative_direction,
            "analyzed_by": analysis.analyzed_by,
        }

    provider_name = metrics.provider_used if metrics else "unknown"

    html = template.render(
        result=result,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        file_exists=lambda p: Path(p).exists(),
        abs_path=lambda p: str(Path(p).resolve()),
        compliance_css=lambda s: _COMPLIANCE_CSS.get(s, "na"),
        compliance_sym=lambda s: _COMPLIANCE_SYMBOL.get(s, "?"),
        product_ids=product_ids,
        metrics=metrics_dict,
        analysis=analysis_dict,
        provider_name=provider_name,
    )
    path = output_dir / "report.html"
    path.write_text(html)
    console.print(f"  [dim]HTML report: {path}[/dim]")
    return path
