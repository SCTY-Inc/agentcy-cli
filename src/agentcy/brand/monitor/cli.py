"""Monitor CLI commands."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from agentcy.brand.cli_utils import emit, pick_format, status

monitor_app = typer.Typer(help="Brand monitoring commands.")
console = Console()


@monitor_app.command("report")
def report(
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    period: str = typer.Option("7d", "--period", "-p", help="Time period"),
    send: bool = typer.Option(False, "--send", help="Send via email"),
    to: list[str] = typer.Option([], "--to", "-t", help="Email recipients"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format: markdown, html, json, yaml"),
) -> None:
    """Generate a brand report."""
    from agentcy.brand.monitor.emailer import send_report
    from agentcy.brand.monitor.reports import (
        format_report_html,
        format_report_markdown,
        generate_report,
    )

    status(f"Generating report for {brand} (period: {period})...")

    report_obj = generate_report(brand, period=period)
    resolved_format = pick_format(format, default="markdown")

    if send and to:
        result = send_report(report_obj, to=to)
        if result.get("success"):
            status(f"[green]Report sent to: {', '.join(to)}[/green]")
        else:
            status(f"[red]Failed to send: {result.get('error')}[/red]")

    if resolved_format == "markdown":
        formatted = format_report_markdown(report_obj)
    elif resolved_format == "html":
        formatted = format_report_html(report_obj)
    elif resolved_format in {"json", "yaml"}:
        payload = emit(report_obj.model_dump(), resolved_format)
        if output and payload is not None:
            output.write_text(payload)
            status(f"Report saved to: {output}")
        return
    else:
        formatted = format_report_markdown(report_obj)

    if output:
        output.write_text(formatted)
        status(f"Report saved to: {output}")
    else:
        console.print(formatted)


@monitor_app.command("analyze")
def analyze(
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    period: str = typer.Option("7d", "--period", "-p", help="Time period"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Analyze brand signals and performance."""
    from agentcy.brand.core.brands import load_brand_config
    from agentcy.brand.signals.history import get_signal_count, query_signals
    from agentcy.brand.signals.relevance import filter_signals

    config = load_brand_config(brand)
    signals = query_signals(brand, since=period, limit=200)
    total_signals = get_signal_count(brand)

    relevant = filter_signals(
        signals,
        keywords=config.get("keywords", []),
        competitors=config.get("competitors", []),
        min_score=0.3,
    )

    learnings = None
    try:
        from agentcy.brand.eval.learnings import get_learnings
    except ImportError:
        pass
    else:
        learnings = get_learnings(brand)

    queue_summary = None
    try:
        from agentcy.brand.publish.queue import get_queue
    except ImportError:
        pass
    else:
        queue_summary = {
            "pending": len(get_queue(brand, status="pending")),
            "posted": len(get_queue(brand, status="posted")),
        }

    payload = {
        "brand": brand,
        "period": period,
        "total_signals": total_signals,
        "signals_in_period": len(signals),
        "relevant_signals": len(relevant),
        "top_signals": [
            {
                "score": signal.get("relevance_score", 0),
                "headline": signal.get("headline", signal.get("title", "")),
                "signal": signal,
            }
            for signal in relevant[:10]
        ],
        "learnings": learnings,
        "queue": queue_summary,
    }
    resolved_format = pick_format(format, default="table")

    if resolved_format != "table":
        emit(payload, resolved_format)
        return

    console.print(f"[bold]Signal Analysis for {brand}[/bold]")
    console.print(f"Period: {period}")
    console.print(f"Total signals in history: {total_signals}")
    console.print(f"Signals in period: {len(signals)}")
    console.print(f"Relevant signals: {len(relevant)}")

    if relevant:
        console.print("\n[bold]Top Signals:[/bold]")
        for signal in relevant[:10]:
            score = signal.get("relevance_score", 0)
            headline = signal.get("headline", signal.get("title", ""))[:60]
            console.print(f"  [{score:.2f}] {headline}")

    if learnings:
        console.print("\n[bold]Content Learnings:[/bold]")
        for dim in learnings.get("weak_dimensions", [])[:3]:
            console.print(f"  - Weak: {dim}")
        for recommendation in learnings.get("recommendations", [])[:3]:
            console.print(f"  - Rec: {recommendation}")

    if queue_summary:
        console.print("\n[bold]Content Queue:[/bold]")
        console.print(f"  Pending: {queue_summary['pending']}")
        console.print(f"  Posted: {queue_summary['posted']}")
