"""prsna CLI - Manage AI personas."""

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from agentcy.persona import __version__
from agentcy.persona.persona import Persona


@dataclass
class OutputMode:
    """Output mode settings."""

    json: bool = False
    quiet: bool = False


_output = OutputMode()

app = typer.Typer(
    name="persona",
    help="Manage, compose, test, and export AI personas.",
    no_args_is_help=True,
)


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", "-V", is_eager=True)
    ] = False,
    json_output: Annotated[
        bool, typer.Option("--json", help="Output as JSON")
    ] = False,
    quiet: Annotated[
        bool, typer.Option("--quiet", "-q", help="Minimal output")
    ] = False,
):
    """Manage, compose, test, and export AI personas."""
    if version:
        typer.echo(f"persona {__version__}")
        raise typer.Exit()
    _output.json = json_output
    _output.quiet = quiet


# Disable colors when not a TTY (for piping)
console = Console(force_terminal=sys.stdout.isatty())

PERSONAS_DIR = Path.home() / ".prsna" / "personas"


def validate_persona_name(name: str) -> str:
    """Validate persona name for safety."""
    if not name or not name.strip():
        raise typer.BadParameter("Persona name cannot be empty")
    # Prevent path traversal
    if "/" in name or "\\" in name or ".." in name:
        raise typer.BadParameter("Persona name cannot contain path separators")
    safe_name = "".join(c for c in name if c.isalnum() or c in "-_")
    if not safe_name:
        raise typer.BadParameter("Persona name must contain alphanumeric characters")
    return safe_name.lower()


def get_persona_path(name: str) -> Path:
    """Get path to persona file."""
    safe_name = validate_persona_name(name)
    return PERSONAS_DIR / f"{safe_name}.yaml"


def load_persona(name: str) -> Persona:
    """Load persona by name."""
    path = get_persona_path(name)
    if not path.exists():
        rprint(f"[red]Persona '{name}' not found[/red]")
        raise typer.Exit(1)
    return Persona.load(path)


@app.command()
def init(
    name: Annotated[str, typer.Argument(help="Name for the new persona")],
    description: Annotated[str, typer.Option("--desc", "-d", help="Description")] = "",
):
    """Create a new empty persona (manual editing required)."""
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)

    persona = Persona(
        name=name,
        description=description or f"A {name} persona",
        traits=["helpful", "knowledgeable"],
        voice={"tone": "professional", "vocabulary": "general", "patterns": []},
    )

    path = get_persona_path(name)
    if path.exists():
        rprint(f"[yellow]Persona '{name}' already exists[/yellow]")
        raise typer.Exit(1)

    persona.save(path)
    rprint(f"[green]Created persona:[/green] {path}")


@app.command()
def create(
    description: Annotated[str, typer.Argument(help="Description of the persona to create")],
    like: Annotated[
        str,
        typer.Option("--like", "-l", help="Real person to base on (uses Exa)"),
    ] = "",
    role: Annotated[str, typer.Option("--role", "-r", help="Job role to base on")] = "",
    name: Annotated[str, typer.Option("--name", "-n", help="Override generated name")] = "",
):
    """Bootstrap a persona using AI.

    Creates a fully-formed persona from a description, real person, or role.
    Uses LLM to generate traits, voice patterns, boundaries, and examples.

    Examples:
        persona create "skeptical investigative journalist"
        persona create --like "Marc Andreessen" "tech investor"
        persona create --role "senior product manager at fintech startup"
    """
    from agentcy.persona.bootstrap import (
        bootstrap_from_description,
        bootstrap_from_person,
        bootstrap_from_role,
    )

    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)

    try:
        if like:
            with console.status(f"[cyan]Researching {like} via Exa...[/cyan]"):
                data = bootstrap_from_person(like)
            rprint(f"[dim]Created persona inspired by: {like}[/dim]")
        elif role:
            with console.status(f"[cyan]Generating persona for role: {role}...[/cyan]"):
                data = bootstrap_from_role(role, description)
        else:
            with console.status(f"[cyan]Generating persona: {description}...[/cyan]"):
                data = bootstrap_from_description(description)

        # Override name if specified
        if name:
            data["name"] = name

        # Create persona from generated data
        persona = Persona(
            name=data.get("name", "unnamed"),
            description=data.get("description", description),
            traits=data.get("traits", []),
            voice=data.get("voice", {}),
            boundaries=data.get("boundaries", []),
            examples=data.get("examples", []),
            context=data.get("context", {}),
        )

        path = get_persona_path(persona.name)
        if path.exists():
            rprint(
                f"[yellow]Persona '{persona.name}' already exists. "
                "Use --name to specify different name.[/yellow]"
            )
            raise typer.Exit(1)

        persona.save(path)
        rprint(f"[green]Created persona:[/green] {persona.name}")
        rprint(f"[dim]Description:[/dim] {persona.description}")
        rprint(f"[dim]Traits:[/dim] {', '.join(persona.traits)}")
        rprint(f"[dim]Saved to:[/dim] {path}")

    except Exception as e:
        rprint(f"[red]Error creating persona:[/red] {e}")
        raise typer.Exit(1)


@app.command("ls")
def list_personas():
    """List all personas."""
    PERSONAS_DIR.mkdir(parents=True, exist_ok=True)

    paths = sorted(PERSONAS_DIR.glob("*.yaml"))
    if not paths:
        if _output.json:
            typer.echo("[]")
        elif not _output.quiet:
            rprint("[dim]No personas found. Use 'persona init <name>' to create one.[/dim]")
        return

    # Load all personas once
    personas = [Persona.load(p) for p in paths]

    if _output.json:
        data = [
            {"name": p.name, "description": p.description, "traits": p.traits}
            for p in personas
        ]
        typer.echo(json.dumps(data, indent=2))
        return

    if _output.quiet:
        for p in personas:
            typer.echo(p.name)
        return

    table = Table(title="Personas")
    table.add_column("Name", style="cyan")
    table.add_column("Description")
    table.add_column("Traits")

    for p in personas:
        table.add_row(p.name, p.description[:40], ", ".join(p.traits[:3]))

    console.print(table)


@app.command()
def show(name: Annotated[str, typer.Argument(help="Persona name")]):
    """Show persona details."""
    persona = load_persona(name)

    if _output.json:
        typer.echo(json.dumps(persona.model_dump(), indent=2))
        return

    if _output.quiet:
        typer.echo(persona.to_prompt())
        return

    rprint(f"[bold cyan]{persona.name}[/bold cyan] v{persona.version}")
    rprint(f"[dim]{persona.description}[/dim]\n")
    rprint(f"[bold]Traits:[/bold] {', '.join(persona.traits)}")
    rprint(f"[bold]Tone:[/bold] {persona.voice.tone}")
    if persona.boundaries:
        rprint("[bold]Boundaries:[/bold]")
        for b in persona.boundaries:
            rprint(f"  - {b}")
    if persona.context:
        rprint(f"\n[bold]Context:[/bold] {persona.context}")


@app.command()
def edit(name: Annotated[str, typer.Argument(help="Persona name")]):
    """Edit persona in $EDITOR."""
    import os
    import subprocess

    path = get_persona_path(name)
    if not path.exists():
        rprint(f"[red]Persona '{name}' not found[/red]")
        raise typer.Exit(1)

    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(path)])


@app.command()
def rm(
    name: Annotated[str, typer.Argument(help="Persona name")],
    force: Annotated[bool, typer.Option("--force", "-f", help="Skip confirmation")] = False,
):
    """Remove a persona."""
    path = get_persona_path(name)
    if not path.exists():
        rprint(f"[red]Persona '{name}' not found[/red]")
        raise typer.Exit(1)

    if not force:
        confirm = typer.confirm(f"Delete persona '{name}'?")
        if not confirm:
            raise typer.Abort()

    path.unlink()
    rprint(f"[green]Removed persona '{name}'[/green]")


@app.command()
def mix(
    first: Annotated[str, typer.Argument(help="First persona")],
    second: Annotated[str, typer.Argument(help="Second persona")],
    output: Annotated[str, typer.Option("--as", "-o", help="Output persona name")] = "",
):
    """Mix two personas into a new one."""
    p1 = load_persona(first)
    p2 = load_persona(second)

    merged = p1.merge_traits(p2)
    if output:
        merged.name = output

    path = get_persona_path(merged.name)
    merged.save(path)
    rprint(f"[green]Created mixed persona:[/green] {merged.name}")
    rprint(f"[dim]Traits: {', '.join(merged.traits)}[/dim]")


@app.command()
def chat(
    name: Annotated[str, typer.Argument(help="Persona name")],
    provider: Annotated[str, typer.Option("--provider", "-p", help="LLM provider")] = "",
):
    """Interactive chat with a persona."""
    import litellm

    from agentcy.persona.learning import log_interaction

    persona = load_persona(name)
    model = provider or persona.providers.get("default", "gpt-4o-mini")

    rprint(f"[cyan]Chatting with {persona.name}[/cyan] (model: {model})")
    rprint("[dim]Type 'exit' or Ctrl+C to quit[/dim]\n")

    messages = [{"role": "system", "content": persona.to_prompt()}]

    try:
        while True:
            user_input = console.input("[bold]You:[/bold] ")
            if user_input.lower() in ("exit", "quit", "q"):
                break

            messages.append({"role": "user", "content": user_input})

            response = litellm.completion(model=model, messages=messages)
            assistant_msg = response.choices[0].message.content

            messages.append({"role": "assistant", "content": assistant_msg})
            rprint(f"[bold green]{persona.name}:[/bold green] {assistant_msg}\n")

    except KeyboardInterrupt:
        rprint("\n[dim]Goodbye![/dim]")
    finally:
        # Log interaction for learning (exclude system message)
        if len(messages) > 1:
            log_interaction(persona, messages[1:])


@app.command()
def ask(
    name: Annotated[str, typer.Argument(help="Persona name")],
    question: Annotated[str, typer.Argument(help="Question to ask (use '-' for stdin)")] = "",
    provider: Annotated[str, typer.Option("--provider", "-p", help="LLM provider")] = "",
):
    """Ask a persona a single question.

    Examples:
        persona ask scientist "What is entropy?"
        echo "What is entropy?" | persona ask scientist -
        cat prompt.txt | persona ask scientist -
    """
    import litellm

    # Read from stdin if question is "-"
    if question == "-" or (not question and not sys.stdin.isatty()):
        question = sys.stdin.read().strip()

    if not question:
        rprint("[red]Question required (provide as argument or pipe to stdin)[/red]")
        raise typer.Exit(1)

    persona = load_persona(name)
    model = provider or persona.providers.get("default", "gpt-4o-mini")

    messages = [
        {"role": "system", "content": persona.to_prompt()},
        {"role": "user", "content": question},
    ]

    response = litellm.completion(model=model, messages=messages)
    content = response.choices[0].message.content

    if _output.json:
        typer.echo(json.dumps({
            "persona": name,
            "question": question,
            "response": content,
            "model": model,
        }, indent=2))
    else:
        typer.echo(content)


@app.command("export")
def export_persona(
    name: Annotated[str, typer.Argument(help="Persona name")] = "",
    format: Annotated[
        str,
        typer.Option(
            "--to",
            "-t",
            help="Export format (for example: prompt, eliza, voice-pack)",
        ),
    ] = "prompt",
    list_formats: Annotated[
        bool,
        typer.Option("--list", "-l", help="List available formats"),
    ] = False,
):
    """Export persona to different formats, including canonical voice_pack.v1 JSON."""
    from agentcy.persona.exporters import get_exporter
    from agentcy.persona.exporters import list_formats as get_formats

    if list_formats:
        rprint("[bold]Available export formats:[/bold]")
        for fmt in get_formats():
            rprint(f"  - {fmt}")
        return

    if not name:
        rprint("[red]Persona name required (or use --list)[/red]")
        raise typer.Exit(1)

    persona = load_persona(name)

    try:
        exporter = get_exporter(format)
        output = exporter(persona)
        typer.echo(output)
    except KeyError:
        rprint(f"[red]Unknown format: {format}[/red]")
        rprint("[dim]Use --list to see available formats[/dim]")
        raise typer.Exit(1)


@app.command()
def enrich(
    name: Annotated[str, typer.Argument(help="Persona name")],
    query: Annotated[str, typer.Option("--query", "-q", help="Search query")] = "",
):
    """Enrich persona with current info from Exa.

    Uses Exa's people search to fetch current information about
    a person/role and adds it to the persona's context.

    Requires EXA_API_KEY environment variable.
    """
    from agentcy.persona.enrichment import enrich_from_exa

    persona = load_persona(name)

    with console.status(f"[cyan]Enriching {name} via Exa...[/cyan]"):
        enriched = enrich_from_exa(persona, query or None)

    # Save updated persona
    path = get_persona_path(name)
    enriched.save(path)

    rprint(f"[green]Enriched persona '{name}'[/green]")
    if enriched.context.get("sources"):
        rprint("[dim]Sources:[/dim]")
        for src in enriched.context["sources"]:
            rprint(f"  - {src}")
    if enriched.context.get("highlights"):
        rprint("[dim]Highlights:[/dim]")
        for h in enriched.context["highlights"][:3]:
            rprint(f"  - {h[:100]}...")


@app.command()
def test(
    name: Annotated[str, typer.Argument(help="Persona name")],
    samples: Annotated[
        int,
        typer.Option("--samples", "-n", help="Number of generated test samples"),
    ] = 5,
    difficulty: Annotated[
        str,
        typer.Option("--difficulty", help="Generated eval tier: basic, mixed, or stress"),
    ] = "mixed",
    cases: Annotated[
        str,
        typer.Option("--cases", help="Path to custom eval cases JSON"),
    ] = "",
    save_report: Annotated[
        bool,
        typer.Option("--save-report", help="Persist the eval report under ~/.prsna/evals"),
    ] = False,
):
    """Test persona consistency with structured eval cases.

    Generated tiers are cumulative:
    - basic: simple identity/value checks
    - mixed: adds ambiguity and tradeoff cases
    - stress: adds boundary and adversarial pressure

    Requires OPENAI_API_KEY environment variable.
    """
    import dspy

    from agentcy.persona.eval_cases import load_eval_cases
    from agentcy.persona.eval_store import save_eval_report
    from agentcy.persona.optimization import test_persona

    persona = load_persona(name)
    custom_cases = load_eval_cases(cases) if cases else None

    # Configure DSPy
    lm = dspy.LM("openai/gpt-4o-mini")
    dspy.configure(lm=lm)

    case_count = len(custom_cases) if custom_cases is not None else samples
    with console.status(f"[cyan]Testing {name} ({case_count} cases, {difficulty})...[/cyan]"):
        results = test_persona(
            persona,
            num_samples=samples,
            cases=custom_cases,
            difficulty=difficulty,
        )

    if save_report:
        report_path = save_eval_report(name, results)
        results = {**results, "report_path": str(report_path)}

    if _output.json:
        typer.echo(json.dumps(results, indent=2))
        return

    score_color = (
        "green"
        if results["score"] > 0.7
        else "yellow"
        if results["score"] > 0.4
        else "red"
    )
    rprint(f"\n[bold]Persona:[/bold] {results['persona']}")
    rprint(f"[bold]Score:[/bold] [{score_color}]{results['score']:.1%}[/{score_color}]")
    rprint(f"[bold]Passed:[/bold] {results['passed']}/{results['total']}")
    rprint(f"[bold]Tier:[/bold] {results['difficulty']}")
    rprint(f"[bold]Boundary pass rate:[/bold] {results['boundary_pass_rate']:.1%}")

    if results.get("bucket_scores"):
        rprint("\n[bold]Bucket scores:[/bold]")
        for bucket, score in results["bucket_scores"].items():
            rprint(f"  - {bucket}: {score:.1%}")

    if results.get("failure_modes"):
        rprint("\n[bold]Failure modes:[/bold]")
        for issue in results["failure_modes"][:5]:
            rprint(f"  - {issue}")

    if results["details"]:
        rprint("\n[bold]Sample responses:[/bold]")
        for d in results["details"][:3]:
            status = "[green]✓[/green]" if d["score"] > 0.5 else "[red]✗[/red]"
            rprint(f"  {status} {d['message'][:40]}...")
            rprint(f"     [dim]{d['response'][:60]}...[/dim]")

    if results.get("report_path"):
        rprint(f"\n[dim]Saved report:[/dim] {results['report_path']}")


@app.command()
def evals(
    name: Annotated[str, typer.Argument(help="Persona name")],
    latest: Annotated[
        bool,
        typer.Option(
            "--latest",
            help="Show the latest saved eval report instead of listing reports",
        ),
    ] = False,
    compare: Annotated[
        bool,
        typer.Option(
            "--compare",
            help="Compare the latest two saved eval reports for this persona",
        ),
    ] = False,
    limit: Annotated[
        int,
        typer.Option("--limit", help="Maximum number of saved reports to list"),
    ] = 10,
):
    """Inspect saved eval reports for a persona."""
    from agentcy.persona.eval_store import (
        compare_latest_eval_reports,
        latest_eval_report,
        list_eval_reports,
    )

    if compare:
        comparison = compare_latest_eval_reports(name)
        if comparison is None:
            rprint(f"[yellow]Need at least two eval reports for '{name}' to compare[/yellow]")
            raise typer.Exit(1)
        if _output.json:
            typer.echo(json.dumps(comparison, indent=2))
            return

        rprint(f"[bold]Latest eval comparison for {name}[/bold]")
        for field, delta in comparison["delta"].items():
            if delta is None:
                continue
            sign = "+" if delta >= 0 else ""
            rprint(f"[dim]{field} Δ:[/dim] {sign}{delta:.1%}")
        added = comparison["failure_modes"]["added"]
        removed = comparison["failure_modes"]["removed"]
        if added:
            rprint("[bold]New failure modes:[/bold]")
            for issue in added:
                rprint(f"  + {issue}")
        if removed:
            rprint("[bold]Removed failure modes:[/bold]")
            for issue in removed:
                rprint(f"  - {issue}")
        return

    if latest:
        report = latest_eval_report(name)
        if report is None:
            rprint(f"[yellow]No eval reports found for '{name}'[/yellow]")
            raise typer.Exit(1)
        if _output.json:
            typer.echo(json.dumps(report, indent=2))
            return

        rprint(f"[bold]Latest eval for {name}[/bold]")
        rprint(f"[dim]Score:[/dim] {report.get('score', 0):.1%}")
        rprint(f"[dim]Tier:[/dim] {report.get('difficulty', 'unknown')}")
        if report.get("report_path"):
            rprint(f"[dim]Path:[/dim] {report['report_path']}")
        if report.get("failure_modes"):
            rprint("[bold]Failure modes:[/bold]")
            for issue in report["failure_modes"][:5]:
                rprint(f"  - {issue}")
        return

    reports = list_eval_reports(name, limit=limit)
    payload = {"persona": name, "count": len(reports), "reports": reports}
    if _output.json:
        typer.echo(json.dumps(payload, indent=2))
        return

    if not reports:
        rprint(f"[yellow]No eval reports found for '{name}'[/yellow]")
        return

    rprint(f"[bold]Saved eval reports for {name}[/bold]")
    for report in reports:
        score = report.get("score")
        score_text = f"{score:.1%}" if isinstance(score, (int, float)) else "n/a"
        rprint(
            f"  - {report.get('saved_at', 'unknown time')} | "
            f"{report.get('difficulty', 'unknown')} | {score_text}"
        )
        rprint(f"    {report['path']}")


@app.command()
def optimize(
    name: Annotated[str, typer.Argument(help="Persona name")],
    iterations: Annotated[int, typer.Option("--iterations", "-i", help="Max iterations")] = 30,
):
    """Optimize persona prompt using GEPA.

    Uses genetic-pareto optimization to evolve the persona prompt
    for better consistency and fidelity.

    Requires OPENAI_API_KEY environment variable and gepa package.
    """
    import dspy

    from agentcy.persona.optimization import optimize_persona

    persona = load_persona(name)

    # Create training examples from persona's own examples
    trainset = []
    for ex in persona.examples:
        trainset.append(
            dspy.Example(
                persona=persona.to_prompt(),
                message=ex.get("user", ""),
                response=ex.get("assistant", ex.get("response", "")),
            ).with_inputs("persona", "message")
        )

    if len(trainset) < 3:
        rprint(
            "[yellow]Warning: Few examples in persona. "
            "Add more for better optimization.[/yellow]"
        )
        # Add generic test messages
        for msg in ["Hello", "Tell me about yourself", "What do you think?"]:
            trainset.append(
                dspy.Example(persona=persona.to_prompt(), message=msg, response="").with_inputs(
                    "persona", "message"
                )
            )

    rprint(f"[cyan]Optimizing {name} with GEPA ({iterations} iterations)...[/cyan]")
    rprint("[dim]This may take a few minutes...[/dim]\n")

    optimized = optimize_persona(persona, trainset, max_iterations=iterations)

    # Save optimized persona
    path = get_persona_path(name)
    optimized.version += 1
    optimized.save(path)

    rprint(f"[green]Optimized persona '{name}' (now v{optimized.version})[/green]")
    rprint("[dim]New description:[/dim]")
    rprint(f"  {optimized.description[:200]}...")


@app.command()
def learn(
    name: Annotated[str, typer.Argument(help="Persona name")],
    apply: Annotated[bool, typer.Option("--apply", "-a", help="Auto-apply learnings")] = False,
):
    """Analyze interactions and improve persona.

    Reviews logged conversations to find patterns and suggests
    improvements to traits, voice, and boundaries.

    Use --apply to automatically apply high-confidence suggestions.
    """
    from agentcy.persona.learning import LearningState, analyze_interactions, apply_learnings

    persona = load_persona(name)
    state = LearningState.load(name)

    if len(state.interactions) < 3:
        rprint(
            "[yellow]Need at least 3 logged interactions to learn. "
            f"Current: {len(state.interactions)}[/yellow]"
        )
        rprint("[dim]Use 'persona chat' to have conversations (they're logged automatically)[/dim]")
        raise typer.Exit(1)

    with console.status(f"[cyan]Analyzing {len(state.interactions)} interactions...[/cyan]"):
        learnings = analyze_interactions(persona)

    if "error" in learnings:
        rprint(f"[red]{learnings['error']}[/red]")
        raise typer.Exit(1)

    rprint(f"\n[bold]Learnings for {name}:[/bold]")

    if learnings.get("effective_patterns"):
        rprint("\n[green]Effective patterns:[/green]")
        for p in learnings["effective_patterns"][:3]:
            rprint(f"  + {p}")

    if learnings.get("suggested_traits"):
        rprint("\n[cyan]Suggested traits:[/cyan]")
        for t in learnings["suggested_traits"]:
            rprint(f"  + {t}")

    if learnings.get("suggested_boundaries"):
        rprint("\n[yellow]Suggested boundaries:[/yellow]")
        for b in learnings["suggested_boundaries"]:
            rprint(f"  + {b}")

    confidence = learnings.get("confidence", 0)
    rprint(f"\n[dim]Confidence: {confidence:.0%}[/dim]")

    if apply:
        updated = apply_learnings(persona, learnings, auto_apply=True)
        path = get_persona_path(name)
        updated.save(path)
        rprint(f"\n[green]Applied learnings to {name} (now v{updated.version})[/green]")
    else:
        rprint("\n[dim]Use --apply to apply these suggestions[/dim]")


@app.command()
def critique(
    name: Annotated[str, typer.Argument(help="Persona name")],
    apply: Annotated[bool, typer.Option("--apply", "-a", help="Auto-apply suggestions")] = False,
):
    """Self-critique persona and suggest improvements.

    Uses a stronger model to deeply analyze the persona definition
    and suggest structural improvements.
    """
    from agentcy.persona.learning import apply_learnings, self_critique

    persona = load_persona(name)

    with console.status(f"[cyan]Self-critiquing {name}...[/cyan]"):
        critique_result = self_critique(persona, model="gpt-4o")

    rprint(f"\n[bold]Self-critique for {name}:[/bold]")
    rprint(f"[dim]Priority: {critique_result.get('priority', 'unknown')}[/dim]\n")

    if critique_result.get("trait_changes"):
        rprint("[cyan]Trait changes:[/cyan]")
        for c in critique_result["trait_changes"]:
            action = c.get("action", "?")
            symbol = "+" if action == "add" else "-" if action == "remove" else "~"
            rprint(f"  {symbol} {c.get('trait')}: {c.get('reason', '')[:50]}")

    if critique_result.get("voice_changes"):
        rprint("\n[cyan]Voice changes:[/cyan]")
        for c in critique_result["voice_changes"]:
            rprint(f"  {c.get('field')}: {c.get('suggestion', '')[:50]}")

    if critique_result.get("description_rewrite"):
        rprint("\n[cyan]Suggested description:[/cyan]")
        rprint(f"  {critique_result['description_rewrite'][:100]}...")

    if apply:
        updated = apply_learnings(persona, critique_result, auto_apply=True)
        path = get_persona_path(name)
        updated.save(path)
        rprint(f"\n[green]Applied critique to {name} (now v{updated.version})[/green]")
    else:
        rprint("\n[dim]Use --apply to apply these suggestions[/dim]")


@app.command()
def drift(
    name: Annotated[str, typer.Argument(help="Persona name")],
    response: Annotated[str, typer.Argument(help="Response text to check")],
):
    """Check if a response drifts from persona.

    Analyzes a single response for consistency with the persona's
    traits, voice, and boundaries.
    """
    from agentcy.persona.drift import detect_drift

    persona = load_persona(name)

    with console.status("[cyan]Checking for drift...[/cyan]"):
        score = detect_drift(persona, response)

    status = "[green]Consistent[/green]" if score.consistent else "[red]Drift detected[/red]"
    rprint(f"\n{status}")
    rprint(f"[dim]Drift score: {score.drift_score:.1%}[/dim]")

    if score.dimension_scores:
        rprint("\n[bold]Dimensions:[/bold]")
        for dim, val in score.dimension_scores.items():
            color = "green" if val < 0.3 else "yellow" if val < 0.6 else "red"
            rprint(f"  {dim}: [{color}]{val:.1%}[/{color}]")

    if score.issues:
        rprint("\n[bold]Issues:[/bold]")
        for issue in score.issues:
            rprint(f"  - {issue}")


if __name__ == "__main__":
    app()
