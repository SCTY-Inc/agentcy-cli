"""CLI commands for autonomous loop and decision management."""

from __future__ import annotations

import asyncio

import typer
from rich.console import Console
from rich.table import Table

from agentcy.brand.cli_utils import emit
from agentcy.brand.core.config import utc_now

console = Console()

# Loop management
loop_app = typer.Typer(help="Autonomous loop management.")

# Learning/metrics management
learn_app = typer.Typer(help="Learning and self-improvement metrics.")


@loop_app.command("start")
def loop_start(
    brands: list[str] | None = typer.Option(None, "--brand", "-b", help="Brands to process"),
    interval: int = typer.Option(300, "--interval", "-i", help="Signal fetch interval (seconds)"),
    foreground: bool = typer.Option(True, "--foreground", "-f", help="Run in foreground"),
) -> None:
    """Start the autonomous loop.

    Runs continuously, processing signals and executing decisions
    within policy boundaries.

    Examples:
        agentcy-compass loop start
        agentcy-compass loop start --brand acme --brand beta
        agentcy-compass loop start --interval 60
    """
    from agentcy.brand.loop import AutonomousLoop, LoopConfig, LoopEvent

    config = LoopConfig(
        brands=brands or [],
        signal_fetch_interval=interval,
    )

    if not foreground:
        raise typer.BadParameter(
            "Background mode is not implemented yet; rerun without --no-foreground."
        )

    loop = AutonomousLoop(config)

    # Event logger
    def log_event(event: LoopEvent) -> None:
        timestamp = event.timestamp.strftime("%H:%M:%S")
        brand = f"[cyan]{event.brand}[/cyan]" if event.brand else ""

        if event.event_type == "loop_started":
            console.print(f"[green]{timestamp} Loop started[/green]")
        elif event.event_type == "loop_stopped":
            console.print(f"[yellow]{timestamp} Loop stopped[/yellow]")
        elif event.event_type == "cycle_completed":
            console.print(f"{timestamp} Cycle {event.details.get('cycles', 0)} completed")
        elif event.event_type == "decision_executed":
            console.print(
                f"{timestamp} [green]EXECUTED[/green] {brand} "
                f"{event.details.get('decision_type', 'unknown')}"
            )
        elif event.event_type == "decision_escalated":
            console.print(
                f"{timestamp} [yellow]ESCALATED[/yellow] {brand} "
                f"priority={event.details.get('priority', 'normal')}"
            )
        elif event.event_type == "decision_denied":
            console.print(f"{timestamp} [red]DENIED[/red] {brand}")
        elif "error" in event.event_type:
            console.print(f"{timestamp} [red]ERROR[/red] {event.details.get('error', '')}")

    loop.on_event(log_event)

    console.print("[bold]Compass Autonomous Loop[/bold]")
    console.print(f"Brands: {', '.join(brands) if brands else 'all'}")
    console.print(f"Interval: {interval}s")
    console.print("Press Ctrl+C to stop\n")

    try:
        asyncio.run(loop.start())
    except KeyboardInterrupt:
        console.print("\n[yellow]Shutting down...[/yellow]")


@loop_app.command("status")
def loop_status() -> None:
    """Show loop status (if running via systemd/docker)."""
    console.print("[yellow]Loop status is only available when running in a container.[/yellow]")
    console.print("\nTo check Docker status:")
    console.print("  docker compose ps")
    console.print("  docker compose logs -f loop")


@loop_app.command("test")
def loop_test(
    brand: str = typer.Argument(..., help="Brand to test"),
    dry_run: bool = typer.Option(True, "--dry-run/--execute", help="Dry run without executing"),
) -> None:
    """Test a single cycle for a brand.

    Useful for validating configuration without starting the full loop.
    """
    from agentcy.brand.core.config import load_brand_config
    from agentcy.brand.core.policy import get_policy_engine

    console.print(f"[bold]Testing loop for brand: {brand}[/bold]\n")

    # Load brand config
    config = load_brand_config(brand)
    if not config:
        console.print(f"[red]Brand not found: {brand}[/red]")
        raise typer.Exit(1)

    console.print("[green]✓[/green] Brand config loaded")

    # Load policy
    engine = get_policy_engine()
    policy = engine.load_policy(brand)
    console.print(f"[green]✓[/green] Policy loaded (enabled={policy.enabled})")
    console.print(f"  Default verdict: {policy.default_verdict.value}")
    console.print(f"  Rules: {len(policy.rules)}")

    # Simulate decision evaluation
    from agentcy.brand.core.decision import Decision, DecisionType

    test_decision = Decision(
        type=DecisionType.CONTENT_PUBLISH,
        brand=brand,
        proposal={"content": "Test content", "platform": "twitter"},
        rationale="Test decision for loop validation",
        confidence=0.85,
        agent_id="test",
    )

    evaluation = engine.evaluate(test_decision, policy, [])
    console.print("\n[bold]Test decision evaluation:[/bold]")
    console.print(f"  Verdict: {evaluation.verdict.value}")
    console.print(f"  Rule matched: {evaluation.rule_matched or 'none'}")
    console.print(f"  Reasons: {', '.join(evaluation.reasons)}")


# Decision management
decision_app = typer.Typer(help="Decision log management.")


@decision_app.command("list")
def decision_list(
    brand: str | None = typer.Option(None, "--brand", "-b", help="Filter by brand"),
    status: str | None = typer.Option(None, "--status", "-s", help="Filter by status"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
    format: str = typer.Option("table", "--format", "-f", help="Output format"),
) -> None:
    """List decisions with optional filters.

    Examples:
        agentcy-compass decision list
        agentcy-compass decision list --brand acme --status pending_review
        agentcy-compass decision list --format json
    """
    from agentcy.brand.core.decision import DecisionStatus, list_decisions

    status_filter = DecisionStatus(status) if status else None
    decisions = list_decisions(brand=brand, status=status_filter, limit=limit)

    if format == "table":
        table = Table(title=f"Decisions ({len(decisions)})")
        table.add_column("ID", style="dim")
        table.add_column("Brand")
        table.add_column("Type")
        table.add_column("Status")
        table.add_column("Confidence")
        table.add_column("Created")

        for d in decisions:
            status_color = {
                "executed": "green",
                "approved": "green",
                "pending_review": "yellow",
                "rejected": "red",
                "failed": "red",
            }.get(d.status.value, "white")

            table.add_row(
                d.id,
                d.brand,
                d.type.value,
                f"[{status_color}]{d.status.value}[/{status_color}]",
                f"{d.confidence:.2f}",
                d.created_at.strftime("%m/%d %H:%M"),
            )

        console.print(table)
    else:
        emit([d.model_dump() for d in decisions], format)


@decision_app.command("show")
def decision_show(
    decision_id: str = typer.Argument(..., help="Decision ID"),
    format: str = typer.Option("yaml", "--format", "-f", help="Output format"),
) -> None:
    """Show decision details."""
    from agentcy.brand.core.decision import get_decision

    decision = get_decision(decision_id)
    if not decision:
        console.print(f"[red]Decision not found: {decision_id}[/red]")
        raise typer.Exit(1)

    emit(decision.model_dump(), format)


@decision_app.command("approve")
def decision_approve(
    decision_id: str = typer.Argument(..., help="Decision ID"),
    reason: str = typer.Option("Manual approval", "--reason", "-r", help="Approval reason"),
    execute: bool = typer.Option(False, "--execute", "-x", help="Execute after approval"),
) -> None:
    """Approve a pending decision.

    Examples:
        agentcy-compass decision approve abc123
        agentcy-compass decision approve abc123 --reason "Reviewed and approved"
        agentcy-compass decision approve abc123 --execute
    """
    from agentcy.brand.workflows.approval import approve_decision

    try:
        decision = approve_decision(decision_id, reviewer="cli", reason=reason)
    except ValueError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)

    if not decision:
        console.print(f"[red]Decision not found: {decision_id}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Approved decision: {decision_id}[/green]")

    if execute:
        console.print(
            "[yellow]Manual execution is still operator-managed; no autonomous handler is wired.[/yellow]"
        )


@decision_app.command("reject")
def decision_reject(
    decision_id: str = typer.Argument(..., help="Decision ID"),
    reason: str = typer.Option(..., "--reason", "-r", help="Rejection reason"),
) -> None:
    """Reject a pending decision.

    Examples:
        agentcy-compass decision reject abc123 --reason "Not aligned with brand voice"
    """
    from agentcy.brand.workflows.approval import reject_decision

    try:
        decision = reject_decision(decision_id, reviewer="cli", reason=reason)
    except ValueError as exc:
        console.print(f"[yellow]{exc}[/yellow]")
        raise typer.Exit(1)

    if not decision:
        console.print(f"[red]Decision not found: {decision_id}[/red]")
        raise typer.Exit(1)

    console.print(f"[red]Rejected decision: {decision_id}[/red]")


@decision_app.command("pending")
def decision_pending(
    brand: str | None = typer.Option(None, "--brand", "-b", help="Filter by brand"),
) -> None:
    """Show decisions pending human review."""
    from agentcy.brand.core.decision import DecisionStatus, list_decisions

    decisions = list_decisions(brand=brand, status=DecisionStatus.PENDING_REVIEW, limit=50)

    if not decisions:
        console.print("[green]No decisions pending review[/green]")
        return

    table = Table(title=f"Pending Review ({len(decisions)})")
    table.add_column("ID", style="dim")
    table.add_column("Brand")
    table.add_column("Type")
    table.add_column("Confidence")
    table.add_column("Reason")
    table.add_column("Age")

    for d in decisions:
        age = utc_now() - d.created_at
        age_str = f"{age.seconds // 3600}h" if age.seconds > 3600 else f"{age.seconds // 60}m"

        table.add_row(
            d.id,
            d.brand,
            d.type.value,
            f"{d.confidence:.2f}",
            (d.review_reason or "")[:40],
            age_str,
        )

    console.print(table)
    console.print("\nTo approve: agentcy-compass decision approve <id>")
    console.print("To reject: agentcy-compass decision reject <id> --reason <reason>")


# Policy management
policy_app = typer.Typer(help="Policy configuration.")


@policy_app.command("show")
def policy_show(
    brand: str = typer.Argument(..., help="Brand name"),
    format: str = typer.Option("yaml", "--format", "-f", help="Output format"),
) -> None:
    """Show policy for a brand."""
    from agentcy.brand.core.policy import get_policy_engine

    engine = get_policy_engine()
    policy = engine.load_policy(brand)

    emit(policy.model_dump(), format)


@policy_app.command("test")
def policy_test(
    brand: str = typer.Argument(..., help="Brand name"),
    decision_type: str = typer.Option("content_publish", "--type", "-t", help="Decision type"),
    confidence: float = typer.Option(0.75, "--confidence", "-c", help="Confidence score"),
) -> None:
    """Test policy evaluation for a hypothetical decision.

    Examples:
        agentcy-compass policy test acme
        agentcy-compass policy test acme --type threat_response --confidence 0.9
    """
    from agentcy.brand.core.decision import Decision, DecisionType
    from agentcy.brand.core.policy import get_policy_engine

    engine = get_policy_engine()
    policy = engine.load_policy(brand)

    decision = Decision(
        type=DecisionType(decision_type),
        brand=brand,
        proposal={"test": True},
        rationale="Policy test decision",
        confidence=confidence,
    )

    evaluation = engine.evaluate(decision, policy, [])

    verdict_color = {
        "allow": "green",
        "escalate": "yellow",
        "deny": "red",
    }.get(evaluation.verdict.value, "white")

    console.print("\n[bold]Policy Evaluation Result[/bold]")
    console.print(f"  Decision type: {decision_type}")
    console.print(f"  Confidence: {confidence}")
    console.print(f"  Verdict: [{verdict_color}]{evaluation.verdict.value}[/{verdict_color}]")
    console.print(f"  Rule matched: {evaluation.rule_matched or 'none'}")
    console.print("  Reasons:")
    for reason in evaluation.reasons:
        console.print(f"    - {reason}")


@policy_app.command("templates")
def policy_templates() -> None:
    """Show available policy templates."""
    from agentcy.brand.core.policy import (
        default_autonomous_policy,
        default_balanced_policy,
        default_conservative_policy,
    )

    console.print("[bold]Available Policy Templates[/bold]\n")

    templates = [
        ("conservative", default_conservative_policy, "Most actions require human review"),
        ("balanced", default_balanced_policy, "Routine actions autonomous, high-stakes escalate"),
        ("autonomous", default_autonomous_policy, "Minimal human intervention"),
    ]

    for name, factory, desc in templates:
        policy = factory("example")
        console.print(f"[cyan]{name}[/cyan]: {desc}")
        console.print(f"  Default verdict: {policy.default_verdict.value}")
        console.print(f"  Min confidence: {policy.global_min_confidence}")
        console.print(f"  Always allow: {[t.value for t in policy.always_allow]}")
        console.print(f"  Always escalate: {[t.value for t in policy.always_escalate]}")
        console.print(f"  Rules: {len(policy.rules)}")
        console.print()


@learn_app.command("metrics")
def learn_metrics(
    brand: str = typer.Argument(..., help="Brand name"),
    days: int = typer.Option(30, "--days", "-d", help="Days to analyze"),
) -> None:
    """Show learning metrics for a brand.

    Displays decision patterns, approval rates, and recommendations
    for improving autonomous operation.
    """
    from agentcy.brand.core.learning import get_learning_tracker

    tracker = get_learning_tracker()
    metrics = tracker.compute_metrics(brand, days)

    console.print(f"[bold]Learning Metrics: {brand}[/bold]")
    console.print(f"Period: {metrics.period_start.date()} to {metrics.period_end.date()}\n")

    # Volume
    console.print(f"[cyan]Decisions:[/cyan] {metrics.total_decisions}")
    if metrics.decisions_by_type:
        for dt, count in sorted(metrics.decisions_by_type.items()):
            console.print(f"  {dt}: {count}")

    console.print()

    # Rates
    console.print("[cyan]Rates:[/cyan]")
    console.print(f"  Approval: {metrics.approval_rate:.0%}")
    console.print(f"  Rejection: {metrics.rejection_rate:.0%}")
    console.print(f"  Auto-executed: {metrics.auto_executed_rate:.0%}")

    console.print()

    # Confidence calibration
    console.print("[cyan]Confidence Calibration:[/cyan]")
    console.print(f"  Avg approved: {metrics.avg_confidence_approved:.2f}")
    console.print(f"  Avg rejected: {metrics.avg_confidence_rejected:.2f}")
    if metrics.confidence_threshold_recommendation:
        console.print(f"  Recommended threshold: {metrics.confidence_threshold_recommendation:.2f}")

    # Patterns
    if metrics.high_success_decision_types:
        console.print(f"\n[green]High success types:[/green] {', '.join(metrics.high_success_decision_types)}")
    if metrics.low_success_decision_types:
        console.print(f"[red]Low success types:[/red] {', '.join(metrics.low_success_decision_types)}")


@learn_app.command("recommendations")
def learn_recommendations(
    brand: str = typer.Argument(..., help="Brand name"),
    days: int = typer.Option(30, "--days", "-d", help="Days to analyze"),
) -> None:
    """Get actionable recommendations from learning data."""
    from agentcy.brand.core.learning import get_learning_tracker

    tracker = get_learning_tracker()
    recs = tracker.get_recommendations(brand, days)

    console.print(f"[bold]Recommendations: {brand}[/bold]\n")

    if not recs:
        console.print("[green]No recommendations - system is performing well![/green]")
        return

    for i, rec in enumerate(recs, 1):
        console.print(f"{i}. {rec}")
