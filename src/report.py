"""
Reporting module.

Generates:
  - Console summary (via Rich)
  - JSON report file
  - HTML visual report with thumbnails
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

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
               background: #0f0f0f; color: #e0e0e0; padding: 2rem; }
        h1 { font-size: 2rem; margin-bottom: 0.5rem; color: #fff; }
        .subtitle { color: #888; margin-bottom: 2rem; }
        .stats { display: flex; gap: 1.5rem; margin-bottom: 2rem; flex-wrap: wrap; }
        .stat { background: #1a1a2e; padding: 1.2rem 1.8rem; border-radius: 12px;
                border: 1px solid #333; min-width: 150px; }
        .stat .num { font-size: 2rem; font-weight: 700; color: #4fc3f7; }
        .stat .label { font-size: 0.85rem; color: #999; margin-top: 4px; }
        .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
                gap: 1.5rem; margin-top: 1rem; }
        .card { background: #1a1a2e; border-radius: 12px; overflow: hidden;
                border: 1px solid #333; transition: transform 0.2s; }
        .card:hover { transform: translateY(-4px); border-color: #4fc3f7; }
        .card img { width: 100%; height: 220px; object-fit: cover; }
        .card-body { padding: 1rem; }
        .card-body h3 { font-size: 1rem; margin-bottom: 0.4rem; color: #fff; }
        .card-body .meta { font-size: 0.8rem; color: #888; }
        .badge { display: inline-block; padding: 2px 10px; border-radius: 20px;
                 font-size: 0.75rem; font-weight: 600; margin-right: 6px; }
        .badge.generated { background: #1b5e20; color: #a5d6a7; }
        .badge.reused { background: #0d47a1; color: #90caf9; }
        .badge.failed { background: #b71c1c; color: #ef9a9a; }
        .badge.pass { background: #1b5e20; color: #a5d6a7; }
        .badge.warn { background: #e65100; color: #ffcc80; }
        .badge.na { background: #333; color: #888; }
        .notes { font-size: 0.78rem; color: #aaa; margin-top: 6px; }
        .footer { margin-top: 3rem; text-align: center; color: #555; font-size: 0.8rem; }
    </style>
</head>
<body>
    <h1>AdForge Report</h1>
    <p class="subtitle">{{ result.campaign_name }} — Generated {{ timestamp }}</p>

    <div class="stats">
        <div class="stat"><div class="num">{{ result.total_assets }}</div><div class="label">Total Assets</div></div>
        <div class="stat"><div class="num">{{ result.generated_count }}</div><div class="label">Generated</div></div>
        <div class="stat"><div class="num">{{ result.reused_count }}</div><div class="label">Reused</div></div>
        <div class="stat"><div class="num">{{ result.failed_count }}</div><div class="label">Failed</div></div>
        <div class="stat"><div class="num">{{ "%.1f"|format(result.elapsed_seconds) }}s</div><div class="label">Elapsed</div></div>
    </div>

    {% if result.warnings %}
    <div style="background:#332200;border:1px solid #665500;border-radius:8px;padding:1rem;margin-bottom:2rem;">
        <strong>⚠ Warnings:</strong>
        <ul style="margin-top:0.5rem;padding-left:1.5rem;">
        {% for w in result.warnings %}
            <li style="color:#ffcc80;">{{ w }}</li>
        {% endfor %}
        </ul>
    </div>
    {% endif %}

    <h2 style="margin-bottom:1rem;">Generated Assets</h2>
    <div class="grid">
    {% for asset in result.assets %}
        <div class="card">
            {% if asset.file_path and file_exists(asset.file_path) %}
            <img src="file://{{ abs_path(asset.file_path) }}" alt="{{ asset.product_id }}">
            {% else %}
            <div style="height:220px;background:#222;display:flex;align-items:center;justify-content:center;color:#555;">No preview</div>
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
                {% if asset.legal_compliance.notes %}
                <div class="notes">{{ asset.legal_compliance.notes | join('; ') }}</div>
                {% endif %}
                {% if asset.prompt_used %}
                <div class="notes" style="margin-top:4px;"><em>Prompt: {{ asset.prompt_used[:120] }}…</em></div>
                {% endif %}
            </div>
        </div>
    {% endfor %}
    </div>

    <div class="footer">AdForge — report generated automatically</div>
</body>
</html>
"""


def print_console_report(result: PipelineResult) -> None:
    """Print a rich summary table to the console."""
    console.print()
    console.print(Panel.fit(
        f"[bold white]{result.campaign_name}[/bold white]\n"
        f"Total: {result.total_assets} | "
        f"[green]Generated: {result.generated_count}[/green] | "
        f"[blue]Reused: {result.reused_count}[/blue] | "
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


def save_json_report(result: PipelineResult, output_dir: Path) -> Path:
    """Save pipeline results as JSON."""
    path = output_dir / "report.json"
    path.write_text(result.model_dump_json(indent=2))
    console.print(f"  [dim]JSON report: {path}[/dim]")
    return path


def save_html_report(result: PipelineResult, output_dir: Path) -> Path:
    """Render and save an HTML report with thumbnails."""
    template = Template(HTML_TEMPLATE)
    html = template.render(
        result=result,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        file_exists=lambda p: Path(p).exists(),
        abs_path=lambda p: str(Path(p).resolve()),
        compliance_css=lambda s: _COMPLIANCE_CSS.get(s, "na"),
        compliance_sym=lambda s: _COMPLIANCE_SYMBOL.get(s, "?"),
    )
    path = output_dir / "report.html"
    path.write_text(html)
    console.print(f"  [dim]HTML report: {path}[/dim]")
    return path
