"""Persona CLI commands."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from brand_os.cli_utils import emit, pick_format, scope_note, status

persona_app = typer.Typer(help="Persona management commands (deprecated; prefer agentcy-vox).")
console = Console()


@persona_app.callback()
def persona_callback() -> None:
    scope_note("agentcy-compass persona surfaces are deprecated; prefer agentcy-vox.")


@persona_app.command("create")
def create(
    description: str = typer.Argument(..., help="Description or name for the persona"),
    name: str | None = typer.Option(None, "--as", "-n", help="Name for the persona"),
    from_person: bool = typer.Option(False, "--from-person", help="Treat description as a real person's name"),
    from_role: bool = typer.Option(False, "--from-role", help="Treat description as a professional role"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format: json, yaml"),
) -> None:
    """Create a new persona using AI generation."""
    from brand_os.persona.crud import create_persona

    persona = create_persona(
        description=description,
        name=name,
        from_person=from_person,
        from_role=from_role,
    )
    emit(persona, pick_format(format, default="yaml"))


@persona_app.command("init")
def init(
    name: str = typer.Argument(..., help="Name for the persona"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Create an empty persona template."""
    from brand_os.persona.crud import init_persona

    persona = init_persona(name)
    status(f"Created persona template: {name}")
    emit(persona, pick_format(format, default="yaml"))


@persona_app.command("list")
def list_personas(
    format: str | None = typer.Option(None, "--format", "-f", help="Output format: table, json, yaml"),
) -> None:
    """List all available personas."""
    from brand_os.persona.crud import list_personas as _list_personas

    names = _list_personas()
    resolved_format = pick_format(format, default="table")

    if resolved_format == "table":
        table = Table(title="Personas")
        table.add_column("Name")
        for name in names:
            table.add_row(name)
        console.print(table)
        return

    emit(names, resolved_format)


@persona_app.command("show")
def show(
    name: str = typer.Argument(..., help="Persona name"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Show a persona's details."""
    from brand_os.persona.crud import load_persona

    persona = load_persona(name)
    emit(persona, pick_format(format, default="yaml"))


@persona_app.command("edit")
def edit(
    name: str = typer.Argument(..., help="Persona name"),
) -> None:
    """Open a persona in the default editor."""
    from brand_os.persona.crud import get_persona_path

    path = get_persona_path(name)
    if not path.exists():
        status(f"[red]Persona not found: {name}[/red]")
        raise typer.Exit(1)

    typer.launch(str(path))


@persona_app.command("delete")
def delete(
    name: str = typer.Argument(..., help="Persona name"),
    force: bool = typer.Option(False, "--force", "-f", help="Skip confirmation"),
) -> None:
    """Delete a persona."""
    from brand_os.persona.crud import delete_persona

    if not force:
        confirm = typer.confirm(f"Delete persona '{name}'?")
        if not confirm:
            raise typer.Abort()

    if delete_persona(name):
        status(f"Deleted persona: {name}")
    else:
        status(f"[red]Persona not found: {name}[/red]")
        raise typer.Exit(1)


@persona_app.command("chat")
def chat(
    name: str = typer.Argument(..., help="Persona name"),
    model: str | None = typer.Option(None, "--model", "-m", help="Model to use"),
) -> None:
    """Start an interactive chat with a persona."""
    from brand_os.persona.chat import Conversation

    conv = Conversation(name, model=model)
    console.print(f"[bold]Chatting with {name}[/bold] (Ctrl+C to exit)")
    console.print()

    try:
        while True:
            user_input = console.input("[bold blue]You:[/bold blue] ")
            if not user_input.strip():
                continue

            response = conv.send(user_input)
            console.print(f"[bold green]{name}:[/bold green] {response}")
            console.print()
    except KeyboardInterrupt:
        console.print("\n[dim]Chat ended.[/dim]")


@persona_app.command("ask")
def ask(
    name: str = typer.Argument(..., help="Persona name"),
    prompt: str = typer.Argument(..., help="The prompt to send"),
    model: str | None = typer.Option(None, "--model", "-m", help="Model to use"),
) -> None:
    """Send a one-shot query to a persona."""
    from brand_os.persona.chat import ask as _ask

    response = _ask(name, prompt, model=model)
    console.print(response)


@persona_app.command("export")
def export(
    name: str = typer.Argument(..., help="Persona name"),
    to: str = typer.Option("yaml", "--to", "-t", help="Export format: json, yaml, eliza, ollama, hub, v2, system_prompt, markdown"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file path"),
) -> None:
    """Export a persona to a specific format."""
    from brand_os.persona.crud import load_persona
    from brand_os.persona.exporters import export_persona

    persona = load_persona(name)
    exported = export_persona(persona, to)

    if output:
        output.write_text(exported)
        status(f"Exported to: {output}")
    else:
        console.print(exported)


@persona_app.command("enrich")
def enrich(
    name: str = typer.Argument(..., help="Persona name"),
    source: str = typer.Option("exa", "--source", "-s", help="Data source: exa"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Enrich a persona with external data."""
    from brand_os.persona.enrichment import enrich_persona

    persona = enrich_persona(name, source=source)
    emit(persona, pick_format(format, default="yaml"))


@persona_app.command("mix")
def mix(
    name1: str = typer.Argument(..., help="First persona"),
    name2: str = typer.Argument(..., help="Second persona"),
    new_name: str = typer.Option(..., "--as", help="Name for the mixed persona"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Mix two personas into a new one."""
    from brand_os.core.llm import complete_json
    from brand_os.persona.crud import load_persona, save_persona

    p1 = load_persona(name1)
    p2 = load_persona(name2)

    prompt = f"""Mix these two personas into a new one named '{new_name}'.

Persona 1: {p1}
Persona 2: {p2}

Create a balanced blend that combines their best traits."""

    default = {
        "name": new_name,
        "traits": [],
        "voice": {},
        "boundaries": [],
        "examples": [],
    }

    mixed = complete_json(prompt=prompt, default=default)
    mixed["name"] = new_name
    mixed["version"] = 1
    mixed["providers"] = {"default": "gpt-4o-mini"}

    save_persona(new_name, mixed)
    emit(mixed, pick_format(format, default="yaml"))


@persona_app.command("test")
def test(
    name: str = typer.Argument(..., help="Persona name"),
    cases_file: Path | None = typer.Option(None, "--cases", "-c", help="JSON file with test cases"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Test persona consistency."""
    import json

    from brand_os.persona.optimization import test_persona_consistency

    if cases_file:
        test_cases = json.loads(cases_file.read_text())
    else:
        test_cases = [
            {"input": "Hello, how are you?"},
            {"input": "What do you think about this topic?"},
            {"input": "Can you help me with something?"},
        ]

    results = test_persona_consistency(name, test_cases)
    resolved_format = pick_format(format, default="table")

    if resolved_format == "table":
        console.print(f"[bold]Test Results for {name}[/bold]")
        console.print(f"Passed: {results['passed']}/{results['total']}")

        table = Table()
        table.add_column("Input")
        table.add_column("Consistent")
        table.add_column("Confidence")
        table.add_column("Status")

        for case in results["cases"]:
            case_status = "[green]PASS[/green]" if case["passed"] else "[red]FAIL[/red]"
            table.add_row(
                case["input"][:50],
                str(case["is_consistent"]),
                f"{case['confidence']:.2f}",
                case_status,
            )
        console.print(table)
        return

    emit(results, resolved_format)


@persona_app.command("optimize")
def optimize(
    name: str = typer.Argument(..., help="Persona name"),
    method: str = typer.Option("dspy", "--method", "-m", help="Optimization method: dspy, gepa"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Optimize a persona using automated methods."""
    from brand_os.persona.optimization import optimize_persona

    result = optimize_persona(name, method=method)
    emit(result, pick_format(format, default="yaml"))


@persona_app.command("drift")
def drift(
    name: str = typer.Argument(..., help="Persona name"),
    response: str = typer.Argument(..., help="Response to check"),
    context: str | None = typer.Option(None, "--context", "-c", help="Conversation context"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Check if a response drifts from persona definition."""
    from brand_os.persona.drift import detect_drift

    result = detect_drift(name, response, context=context)
    emit(result.model_dump(), pick_format(format, default="yaml"))


@persona_app.command("learn")
def learn(
    name: str = typer.Argument(..., help="Persona name"),
    apply: bool = typer.Option(False, "--apply", help="Apply suggested improvements"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Generate improvement suggestions from learning history."""
    from brand_os.persona.learning import apply_improvements, suggest_improvements

    improvements = suggest_improvements(name)

    if apply:
        persona = apply_improvements(name, improvements)
        status(f"[green]Applied improvements to {name}[/green]")
        emit(persona, pick_format(format, default="yaml"))
        return

    emit(improvements, pick_format(format, default="yaml"))


@persona_app.command("critique")
def critique(
    name: str = typer.Argument(..., help="Persona name"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Generate a critique of persona performance."""
    from brand_os.persona.learning import critique_persona

    result = critique_persona(name)
    emit(result, pick_format(format, default="yaml"))
