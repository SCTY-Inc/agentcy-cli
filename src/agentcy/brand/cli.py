"""Main CLI entry point for agentcy-compass."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from agentcy.brand.cli_utils import emit, is_json_output, pick_format, set_output_mode, status

# Main app
app = typer.Typer(
    name="agentcy-compass",
    help="CLI-first brand operations toolkit.",
    no_args_is_help=True,
)
console = Console()


@app.callback()
def main(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Prefer JSON output across compatible commands.",
    ),
    json_envelope: bool = typer.Option(
        False,
        "--json-envelope",
        help="Emit normalized JSON envelopes for compatible commands.",
    ),
) -> None:
    set_output_mode(json_output=json_output, envelope=json_envelope)

# Import and register subcommand groups
from agentcy.brand.persona.cli import persona_app
from agentcy.brand.intel.cli import intel_app
from agentcy.brand.signals.cli import signals_app
from agentcy.brand.plan.cli import plan_app
from agentcy.brand.produce.cli import produce_app
from agentcy.brand.eval.cli import eval_app
from agentcy.brand.publish.cli import publish_app, queue_cli_app
from agentcy.brand.monitor.cli import monitor_app
from agentcy.brand.loop_cli import loop_app, decision_app, policy_app, learn_app

app.add_typer(persona_app, name="persona")
app.add_typer(intel_app, name="intel")
app.add_typer(signals_app, name="signals")
app.add_typer(plan_app, name="plan")
app.add_typer(produce_app, name="produce")
app.add_typer(eval_app, name="eval")
app.add_typer(publish_app, name="publish")
app.add_typer(queue_cli_app, name="queue")
app.add_typer(monitor_app, name="monitor")
app.add_typer(loop_app, name="loop")
app.add_typer(decision_app, name="decision")
app.add_typer(policy_app, name="policy")
app.add_typer(learn_app, name="learn")

# Brand management commands
brand_app = typer.Typer(help="Brand management commands.")
app.add_typer(brand_app, name="brand")


@app.command("catalog")
def catalog() -> None:
    """Describe Compass ownership boundaries and preferred surfaces."""
    emit(
        {
            "artifact_owner": "brief.v1",
            "core_stage": "strategy and brief generation",
            "preferred_surfaces": [
                "brand",
                "signals",
                "intel",
                "plan",
            ],
            "secondary_surfaces": [
                "produce",
                "eval",
                "publish",
                "monitor",
            ],
            "deprecated_surfaces": [
                {
                    "command_group": "persona",
                    "replacement": "agentcy-vox",
                    "reason": "persona authoring and testing now belong to vox",
                }
            ],
            "notes": [
                "Compass is the canonical writer for brief.v1.",
                "Use agentcy-vox for persona creation, testing, and export.",
                "Use agentcy-loom for execution/review/publish runtime ownership.",
            ],
        }
    )


@brand_app.command("init")
def brand_init(
    name: str = typer.Argument(..., help="Brand name"),
    directory: Path | None = typer.Option(None, "--dir", "-d", help="Brands directory"),
) -> None:
    """Initialize a new brand from template."""
    import shutil

    from agentcy.brand.core.config import get_config

    config = get_config()
    brands_dir = directory or config.brands_dir

    if not brands_dir.is_absolute():
        brands_dir = Path.cwd() / brands_dir

    brand_dir = brands_dir / name

    if brand_dir.exists():
        if is_json_output():
            emit({"created": False, "brand": name, "error": "brand already exists"})
        else:
            status(f"[red]Brand already exists: {name}[/red]")
        raise typer.Exit(1)

    # Create from template
    template_dir = brands_dir / "_template"
    if template_dir.exists():
        shutil.copytree(template_dir, brand_dir)
    else:
        # Create minimal structure
        brand_dir.mkdir(parents=True)
        (brand_dir / "assets").mkdir()

        # Create brand.yml
        brand_yml = f"""name: {name}
description: ""

voice:
  tone: neutral
  vocabulary: general
  patterns: []

handles: {{}}
keywords: []
competitors: []
"""
        (brand_dir / "brand.yml").write_text(brand_yml)

        # Create rubric.yml
        rubric_yml = """name: default
pass_threshold: 0.7

dimensions:
  - name: clarity
    description: Is the content clear and easy to understand?
    weight: 1.0
    threshold: 0.7

  - name: engagement
    description: Is the content engaging and compelling?
    weight: 1.2
    threshold: 0.7

  - name: brand_voice
    description: Does it match the brand voice?
    weight: 1.0
    threshold: 0.7

red_flags:
  - Offensive content
  - Misleading claims
"""
        (brand_dir / "rubric.yml").write_text(rubric_yml)

    if is_json_output():
        emit({"created": True, "brand": name, "path": str(brand_dir)})
    else:
        status(f"[green]Created brand: {name}[/green]")
        status(f"Location: {brand_dir}")


@brand_app.command("list")
def brand_list(
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """List all available brands."""
    from rich.table import Table

    from agentcy.brand.core.brands import discover_brands, get_brand_dir

    brands = discover_brands()
    resolved_format = pick_format(format, default="table")

    if resolved_format == "table":
        table = Table(title="Brands")
        table.add_column("Name")
        table.add_column("Path")

        for name in brands:
            table.add_row(name, str(get_brand_dir(name)))

        console.print(table)
    else:
        emit(brands, resolved_format)


@brand_app.command("show")
def brand_show(
    name: str = typer.Argument(..., help="Brand name"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Show brand configuration."""
    from agentcy.brand.core.brands import load_brand_config

    config = load_brand_config(name)
    emit(config, format, default="yaml")


@brand_app.command("edit")
def brand_edit(
    name: str = typer.Argument(..., help="Brand name"),
) -> None:
    """Open brand config in editor."""
    from agentcy.brand.core.brands import get_brand_dir

    brand_dir = get_brand_dir(name)

    for filename in ["brand.yml", f"{name}-brand.yml"]:
        config_path = brand_dir / filename
        if config_path.exists():
            typer.launch(str(config_path))
            return

    status(f"[red]Brand config not found: {name}[/red]")
    raise typer.Exit(1)


@brand_app.command("validate")
def brand_validate(
    name: str = typer.Argument(..., help="Brand name"),
) -> None:
    """Validate brand configuration."""
    from agentcy.brand.core.brands import load_brand_profile

    try:
        profile = load_brand_profile(name)
    except Exception as e:
        if is_json_output():
            emit({"valid": False, "brand": name, "error": str(e)})
        else:
            status(f"[red]Validation failed: {e}[/red]")
        raise typer.Exit(1)

    payload = {
        "valid": True,
        "brand": name,
        "name": profile.identity.name,
        "traits": len(profile.identity.traits),
        "keywords": len(profile.keywords or []),
    }
    if is_json_output():
        emit(payload)
    else:
        status(f"[green]Brand '{name}' is valid[/green]")
        status(f"  Name: {profile.identity.name}")
        status(f"  Traits: {len(profile.identity.traits)}")
        status(f"  Keywords: {len(profile.keywords or [])}")


# Config management commands
config_app = typer.Typer(help="Configuration management.")
app.add_typer(config_app, name="config")


@config_app.command("env")
def config_env() -> None:
    """Show environment configuration status."""
    import os

    from rich.table import Table

    env_vars = [
        ("GOOGLE_API_KEY", "Gemini LLM"),
        ("OPENAI_API_KEY", "OpenAI/LiteLLM"),
        ("ANTHROPIC_API_KEY", "Anthropic"),
        ("EXA_API_KEY", "Exa enrichment"),
        ("APIFY_TOKEN", "Apify scraping"),
        ("TWITTER_CONSUMER_KEY", "Twitter publishing"),
        ("LINKEDIN_ACCESS_TOKEN", "LinkedIn publishing"),
        ("RESEND_API_KEY", "Email delivery"),
    ]

    table = Table(title="Environment Variables")
    table.add_column("Variable")
    table.add_column("Purpose")
    table.add_column("Status")

    rows = []
    for var, purpose in env_vars:
        value = os.getenv(var)
        row_status = "[green]Set[/green]" if value else "[red]Not set[/red]"
        table.add_row(var, purpose, row_status)
        rows.append({"variable": var, "purpose": purpose, "set": bool(value)})

    if is_json_output():
        emit({"variables": rows})
    else:
        status(table)


@config_app.command("profiles")
def config_profiles() -> None:
    """List configuration profiles."""
    from agentcy.brand.core.config import get_config

    config = get_config()
    payload = {
        "brands_dir": str(config.brands_dir),
        "data_dir": str(config.data_dir),
        "default_provider": config.default_provider,
        "default_model": config.default_model or "auto",
    }
    if is_json_output():
        emit(payload)
    else:
        status("[bold]Current Configuration[/bold]")
        status(f"  Brands dir: {config.brands_dir}")
        status(f"  Data dir: {config.data_dir}")
        status(f"  Default provider: {config.default_provider}")
        status(f"  Default model: {config.default_model or 'auto'}")


# Version command
@app.command("version")
def version() -> None:
    """Show version information."""
    from agentcy.brand import __version__

    if is_json_output():
        emit({"version": __version__})
    else:
        status(f"agentcy-compass v{__version__}")


if __name__ == "__main__":
    app()
