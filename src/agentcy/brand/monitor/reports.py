"""Report generation."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.llm import complete_json


class BrandReport(BaseModel):
    """Brand intelligence report."""

    brand: str
    report_date: str = Field(default_factory=lambda: utc_now().isoformat()[:10])
    overview: str = ""
    highlights: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    actions: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


REPORT_SYSTEM = """You are a brand intelligence analyst.
Generate a concise report summarizing the brand's signals and performance.

Output JSON with:
- overview: 2-3 sentence summary
- highlights: list of 3-5 key highlights
- metrics: dict of key metrics
- actions: list of recommended actions
- risks: list of potential risks or concerns"""


def generate_report(
    brand: str,
    signals: list[dict[str, Any]] | None = None,
    period: str = "7d",
) -> BrandReport:
    """Generate a brand report.

    Args:
        brand: Brand name
        signals: Optional signals to include (fetches if not provided)
        period: Time period for the report

    Returns:
        BrandReport
    """
    # Load signals if not provided
    if signals is None:
        from agentcy.brand.signals.history import query_signals
        signals = query_signals(brand, since=period, limit=100)

    # Load learnings if available
    learnings = {}
    try:
        from agentcy.brand.eval.learnings import get_learnings
    except ImportError:
        pass
    else:
        learnings = get_learnings(brand)

    # Load queue stats
    queue_stats = {}
    try:
        from agentcy.brand.publish.queue import get_queue
    except ImportError:
        pass
    else:
        pending = len(get_queue(brand, status="pending"))
        posted = len(get_queue(brand, status="posted"))
        queue_stats = {"pending": pending, "posted": posted}

    prompt_parts = [
        f"Generate a brand intelligence report for: {brand}",
        f"Period: {period}",
        "",
        f"## Signals ({len(signals)} total)",
    ]

    for signal in signals[:20]:
        prompt_parts.append(f"- {signal.get('headline', signal.get('title', ''))}")

    if learnings:
        prompt_parts.extend([
            "",
            "## Learnings",
            f"Weak dimensions: {learnings.get('weak_dimensions', [])}",
            f"Patterns: {learnings.get('patterns', [])[:3]}",
        ])

    if queue_stats:
        prompt_parts.extend([
            "",
            "## Content Queue",
            f"Pending: {queue_stats.get('pending', 0)}",
            f"Posted: {queue_stats.get('posted', 0)}",
        ])

    prompt = "\n".join(prompt_parts)

    default = {
        "overview": "No data available for report.",
        "highlights": [],
        "metrics": {},
        "actions": [],
        "risks": [],
    }

    result = complete_json(prompt=prompt, system=REPORT_SYSTEM, default=default)

    return BrandReport(
        brand=brand,
        overview=result.get("overview", ""),
        highlights=result.get("highlights", []),
        metrics=result.get("metrics", {}),
        actions=result.get("actions", []),
        risks=result.get("risks", []),
    )


def format_report_html(report: BrandReport) -> str:
    """Format report as HTML.

    Args:
        report: BrandReport

    Returns:
        HTML string
    """
    html_parts = [
        f"<h1>Brand Report: {report.brand}</h1>",
        f"<p><em>Generated: {report.report_date}</em></p>",
        "",
        "<h2>Overview</h2>",
        f"<p>{report.overview}</p>",
    ]

    if report.highlights:
        html_parts.extend([
            "<h2>Highlights</h2>",
            "<ul>",
            *[f"<li>{h}</li>" for h in report.highlights],
            "</ul>",
        ])

    if report.metrics:
        html_parts.extend([
            "<h2>Metrics</h2>",
            "<ul>",
            *[f"<li><strong>{k}:</strong> {v}</li>" for k, v in report.metrics.items()],
            "</ul>",
        ])

    if report.actions:
        html_parts.extend([
            "<h2>Recommended Actions</h2>",
            "<ul>",
            *[f"<li>{a}</li>" for a in report.actions],
            "</ul>",
        ])

    if report.risks:
        html_parts.extend([
            "<h2>Risks & Concerns</h2>",
            "<ul>",
            *[f"<li>{r}</li>" for r in report.risks],
            "</ul>",
        ])

    return "\n".join(html_parts)


def format_report_markdown(report: BrandReport) -> str:
    """Format report as Markdown.

    Args:
        report: BrandReport

    Returns:
        Markdown string
    """
    md_parts = [
        f"# Brand Report: {report.brand}",
        f"*Generated: {report.report_date}*",
        "",
        "## Overview",
        report.overview,
    ]

    if report.highlights:
        md_parts.extend([
            "",
            "## Highlights",
            *[f"- {h}" for h in report.highlights],
        ])

    if report.metrics:
        md_parts.extend([
            "",
            "## Metrics",
            *[f"- **{k}:** {v}" for k, v in report.metrics.items()],
        ])

    if report.actions:
        md_parts.extend([
            "",
            "## Recommended Actions",
            *[f"- {a}" for a in report.actions],
        ])

    if report.risks:
        md_parts.extend([
            "",
            "## Risks & Concerns",
            *[f"- {r}" for r in report.risks],
        ])

    return "\n".join(md_parts)
