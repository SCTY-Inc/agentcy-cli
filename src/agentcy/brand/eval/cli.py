"""Eval CLI commands."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from agentcy.brand.cli_utils import emit, pick_format, status

eval_app = typer.Typer(help="Content evaluation commands.")
console = Console()


@eval_app.command("grade")
def grade(
    text: str = typer.Argument(..., help="Text to grade (or - for stdin)"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name for rubric"),
    rubric_file: Path | None = typer.Option(None, "--rubric", "-r", help="Custom rubric file"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Grade content against a rubric."""
    import sys

    from agentcy.brand.core.brands import load_brand_rubric
    from agentcy.brand.eval.grader import grade_content
    from agentcy.brand.eval.learnings import log_evaluation
    from agentcy.brand.eval.rubric import load_rubric, parse_rubric

    if text == "-":
        text = sys.stdin.read()

    rubric = None
    if rubric_file:
        rubric = load_rubric(rubric_file)
    elif brand:
        rubric_data = load_brand_rubric(brand)
        if rubric_data:
            rubric = parse_rubric(rubric_data)

    result = grade_content(text, rubric=rubric)

    if brand:
        log_evaluation(brand, text, result.model_dump())

    resolved_format = pick_format(format, default="yaml")
    if resolved_format == "table":
        console.print(f"[bold]Overall Score: {result.overall_score:.2f}[/bold]")
        console.print(f"Passed: {'[green]Yes[/green]' if result.passed else '[red]No[/red]'}")
        console.print()

        table = Table(title="Dimension Scores")
        table.add_column("Dimension")
        table.add_column("Score")
        table.add_column("Status")
        table.add_column("Feedback")

        for dim in result.dimension_scores:
            dimension_status = "[green]PASS[/green]" if dim.passed else "[red]FAIL[/red]"
            table.add_row(dim.name, f"{dim.score:.2f}", dimension_status, dim.feedback[:50])

        console.print(table)

        if result.red_flags_found:
            console.print("\n[red]Red Flags:[/red]")
            for red_flag in result.red_flags_found:
                console.print(f"  - {red_flag}")

        if result.suggestions:
            console.print("\n[yellow]Suggestions:[/yellow]")
            for suggestion in result.suggestions:
                console.print(f"  - {suggestion}")
        return

    emit(result.model_dump(), resolved_format)


@eval_app.command("drift")
def drift(
    persona: str = typer.Argument(..., help="Persona name"),
    response: str = typer.Argument(..., help="Response to check"),
    context: str | None = typer.Option(None, "--context", "-c", help="Conversation context"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Check if a response drifts from persona definition."""
    from agentcy.brand.persona.drift import detect_drift

    result = detect_drift(persona, response, context=context)
    resolved_format = pick_format(format, default="yaml")

    if resolved_format == "table":
        console.print(
            f"[bold]Consistent: {'[green]Yes[/green]' if result.is_consistent else '[red]No[/red]'}[/bold]"
        )
        console.print(f"Confidence: {result.confidence:.2f}")
        console.print(f"Voice Match: {result.voice_match:.2f}")

        if result.boundary_violations:
            console.print("\n[red]Boundary Violations:[/red]")
            for violation in result.boundary_violations:
                console.print(f"  - {violation}")

        if result.suggestions:
            console.print("\n[yellow]Suggestions:[/yellow]")
            for suggestion in result.suggestions:
                console.print(f"  - {suggestion}")
        return

    emit(result.model_dump(), resolved_format)


@eval_app.command("learn")
def learn(
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Aggregate learnings from evaluation history."""
    from agentcy.brand.eval.learnings import aggregate_learnings, load_eval_history

    history = load_eval_history(brand)
    status(f"Analyzing {len(history)} evaluations...")

    learnings = aggregate_learnings(brand)
    resolved_format = pick_format(format, default="yaml")

    if resolved_format == "table":
        if learnings.get("weak_dimensions"):
            console.print("\n[bold]Weak Dimensions:[/bold]")
            for dim in learnings["weak_dimensions"]:
                console.print(f"  - {dim}")

        if learnings.get("patterns"):
            console.print("\n[bold]Patterns:[/bold]")
            for pattern in learnings["patterns"]:
                console.print(f"  - {pattern}")

        if learnings.get("recommendations"):
            console.print("\n[bold]Recommendations:[/bold]")
            for recommendation in learnings["recommendations"]:
                console.print(f"  - {recommendation}")
        return

    emit(learnings, resolved_format)


@eval_app.command("heal")
def heal(
    text: str = typer.Argument(..., help="Text to heal"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name for rubric"),
    max_iterations: int = typer.Option(3, "--max-iter", "-n", help="Maximum iterations"),
    target: float = typer.Option(0.8, "--target", "-t", help="Target score"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Iteratively improve content until it passes."""
    from agentcy.brand.core.brands import load_brand_rubric
    from agentcy.brand.eval.heal import heal_content
    from agentcy.brand.eval.rubric import parse_rubric

    rubric = None
    if brand:
        rubric_data = load_brand_rubric(brand)
        if rubric_data:
            rubric = parse_rubric(rubric_data)

    status(f"Starting healing loop (max {max_iterations} iterations, target {target})...")

    result = heal_content(
        text,
        rubric=rubric,
        max_iterations=max_iterations,
        target_score=target,
    )

    if result["success"]:
        status(
            f"[green]Success![/green] Achieved {result['final_score']:.2f} in {result['iterations']} iterations"
        )
    else:
        status(f"[yellow]Did not reach target.[/yellow] Final score: {result['final_score']:.2f}")

    emit(result, pick_format(format, default="yaml"))
