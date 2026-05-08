"""Plan CLI commands."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from agentcy.brand.cli_utils import emit, pick_format, status

plan_app = typer.Typer(help="Campaign planning commands.")
console = Console()


@plan_app.command("research")
def research_cmd(
    brief: str = typer.Argument(..., help="Campaign brief or research question"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Execute research stage."""
    from agentcy.brand.plan.stages.research import research

    result = research(brief=brief, brand=brand)
    emit(result.model_dump(), format)


@plan_app.command("strategy")
def strategy_cmd(
    input_file: Path | None = typer.Option(None, "--input", "-i", help="Research result JSON"),
    brief: str | None = typer.Option(None, "--brief", help="Brief if no input"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Execute strategy stage."""
    from agentcy.brand.plan.stages.strategy import strategy

    # Read from file, stdin, or use brief
    research_result = None
    if input_file:
        research_result = json.loads(input_file.read_text())
    elif not sys.stdin.isatty():
        research_result = json.load(sys.stdin)

    result = strategy(research_result=research_result, brief=brief, brand=brand)
    emit(result.model_dump(), format)


@plan_app.command("creative")
def creative_cmd(
    input_file: Path | None = typer.Option(None, "--input", "-i", help="Strategy result JSON"),
    brief: str | None = typer.Option(None, "--brief", help="Brief if no input"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Execute creative stage."""
    from agentcy.brand.plan.stages.creative import creative

    strategy_result = None
    if input_file:
        strategy_result = json.loads(input_file.read_text())
    elif not sys.stdin.isatty():
        strategy_result = json.load(sys.stdin)

    result = creative(strategy_result=strategy_result, brief=brief, brand=brand)
    emit(result.model_dump(), format)


@plan_app.command("activation")
def activation_cmd(
    input_file: Path | None = typer.Option(None, "--input", "-i", help="Creative result JSON"),
    brief: str | None = typer.Option(None, "--brief", help="Brief if no input"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Execute activation stage."""
    from agentcy.brand.plan.stages.activation import activation

    creative_result = None
    if input_file:
        creative_result = json.loads(input_file.read_text())
    elif not sys.stdin.isatty():
        creative_result = json.load(sys.stdin)

    result = activation(creative_result=creative_result, brief=brief, brand=brand)
    emit(result.model_dump(), format)


@plan_app.command("run")
def run(
    brief: str = typer.Argument(..., help="Campaign brief"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name"),
    interactive: bool = typer.Option(
        False,
        "--interactive",
        "-i",
        help="Enable human gates",
    ),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output file"),
    brief_v1_output: Path | None = typer.Option(
        None,
        "--brief-v1-output",
        help="Write canonical brief.v1 JSON",
    ),
    voice_pack_id: str | None = typer.Option(
        None,
        "--voice-pack-id",
        help="Canonical voice_pack.v1 lineage ID for brief.v1 emission",
    ),
    voice_pack_input: Path | None = typer.Option(
        None,
        "--voice-pack-input",
        help="Canonical voice_pack.v1 JSON input used as an external voice constraint",
    ),
    brand_id: str | None = typer.Option(
        None,
        "--brand-id",
        help="Canonical brand lineage ID for brief.v1 emission",
    ),
    signal_id: str | None = typer.Option(
        None,
        "--signal-id",
        help="Optional canonical signal lineage ID for brief.v1 emission",
    ),
    signal_source: str | None = typer.Option(
        None,
        "--signal-source",
        help="Optional signal source override for brief.v1 emission",
    ),
    policy_verdict: str = typer.Option(
        "escalate",
        "--policy-verdict",
        help="Policy verdict for brief.v1 emission",
    ),
    policy_confidence: float = typer.Option(
        0.5,
        "--policy-confidence",
        min=0.0,
        max=1.0,
        help="Policy confidence for brief.v1 emission",
    ),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Run full campaign planning pipeline."""
    from agentcy.brand.plan.brief_v1 import build_brief_v1, load_voice_pack_v1, write_brief_v1
    from agentcy.brand.plan.stages.activation import activation
    from agentcy.brand.plan.stages.creative import creative
    from agentcy.brand.plan.stages.research import research
    from agentcy.brand.plan.stages.strategy import strategy
    from agentcy.brand.plan.store import save_campaign

    resolved_format = pick_format(format, default="json")
    status("[bold]Starting campaign pipeline[/bold]")
    status(f"Brief: {brief[:100]}...")

    # Research
    status("\n[bold cyan]Stage 1: Research[/bold cyan]")
    research_result = research(brief=brief, brand=brand)
    status(
        "  Found "
        f"{len(research_result.insights)} insights, "
        f"{len(research_result.competitors)} competitors"
    )

    if interactive:
        if not typer.confirm("Continue to strategy?"):
            raise typer.Abort()

    # Strategy
    status("\n[bold cyan]Stage 2: Strategy[/bold cyan]")
    strategy_result = strategy(research_result=research_result.model_dump(), brand=brand)
    status(f"  Positioning: {strategy_result.positioning[:80]}...")

    if interactive:
        if not typer.confirm("Continue to creative?"):
            raise typer.Abort()

    # Creative
    status("\n[bold cyan]Stage 3: Creative[/bold cyan]")
    creative_result = creative(strategy_result=strategy_result.model_dump(), brand=brand)
    status(
        "  Generated "
        f"{len(creative_result.headlines)} headlines, "
        f"{len(creative_result.ctas)} CTAs"
    )

    if interactive:
        if not typer.confirm("Continue to activation?"):
            raise typer.Abort()

    # Activation
    status("\n[bold cyan]Stage 4: Activation[/bold cyan]")
    activation_result = activation(creative_result=creative_result.model_dump(), brand=brand)
    status(
        "  Planned "
        f"{len(activation_result.channels)} channels, "
        f"{len(activation_result.calendar)} calendar items"
    )

    # Compile results
    full_result = {
        "brief": brief,
        "brand": brand,
        "research": research_result.model_dump(),
        "strategy": strategy_result.model_dump(),
        "creative": creative_result.model_dump(),
        "activation": activation_result.model_dump(),
    }

    # Save campaign
    campaign_id = save_campaign(
        brief=brief,
        brand=brand,
        stages=full_result,
    )
    status(f"\n[green]Campaign saved: {campaign_id}[/green]")

    if brief_v1_output:
        if not voice_pack_id and not voice_pack_input:
            raise typer.BadParameter(
                "--voice-pack-id or --voice-pack-input is required when using --brief-v1-output"
            )

        voice_pack = load_voice_pack_v1(voice_pack_input) if voice_pack_input else None
        brief_v1 = build_brief_v1(
            brief=brief,
            brand=brand,
            voice_pack_id=voice_pack_id,
            campaign_id=campaign_id,
            research_result=research_result.model_dump(),
            strategy_result=strategy_result.model_dump(),
            creative_result=creative_result.model_dump(),
            activation_result=activation_result.model_dump(),
            voice_pack=voice_pack,
            brand_id=brand_id,
            signal_id=signal_id,
            signal_source=signal_source,
            policy_verdict=policy_verdict,
            policy_confidence=policy_confidence,
        )
        write_brief_v1(brief_v1_output, brief_v1)
        full_result["brief_v1"] = brief_v1.model_dump(exclude_none=True, by_alias=True)
        status(f"[green]brief.v1 saved: {brief_v1_output}[/green]")

    # Output
    if output:
        output.write_text(json.dumps(full_result, indent=2, ensure_ascii=False))
        status(f"Results saved to: {output}")
    else:
        emit(full_result, resolved_format)


@plan_app.command("list")
def list_cmd(
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """List saved campaigns."""
    from agentcy.brand.plan.store import list_campaigns

    campaigns = list_campaigns()
    resolved_format = pick_format(format, default="table")

    if resolved_format == "table":
        table = Table(title="Campaigns")
        table.add_column("ID")
        table.add_column("Brief")
        table.add_column("Brand")
        table.add_column("Stages")
        table.add_column("Created")

        for c in campaigns:
            table.add_row(
                c["id"],
                c["brief"][:40] + "..." if len(c.get("brief", "")) > 40 else c.get("brief", ""),
                c.get("brand") or "",
                ", ".join(c.get("stages", [])),
                c.get("created_at", "")[:10],
            )
        console.print(table)
    else:
        emit(campaigns, resolved_format)


@plan_app.command("resume")
def resume(
    campaign_id: str = typer.Argument(..., help="Campaign ID to resume"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Resume a saved campaign."""
    from agentcy.brand.plan.store import load_campaign

    campaign = load_campaign(campaign_id)
    status(f"[bold]Loaded campaign: {campaign_id}[/bold]")
    status(f"Brief: {campaign.get('brief', '')[:100]}")
    status(f"Completed stages: {list(campaign.get('stages', {}).keys())}")

    emit(campaign, format)
