"""agentcy — dispatcher CLI.

Each member subcommand delegates to its member binary via subprocess,
passing all arguments through verbatim. JSON output, exit codes,
and signals are forwarded unchanged.

Pipeline:
    agentcy voice export <persona> --to voice-pack.v1 --json
    agentcy briefs plan --brand <id> --json
    agentcy forecast run --files docs/ --brief brief.v1.json --json
    agentcy studio run social.post --brand <id> --json
    agentcy measure adapt --run-result run.json --sidecar s.json --json
    agentcy measure calibrate --forecast f.json --performance p.json
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from agentcy_protocols.output import envelope as _envelope
from agentcy_protocols.utils import utc_now_iso
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="agentcy",
    help="Agent-native brand ops stack — voice | briefs | forecast | studio | measure",
    no_args_is_help=True,
    add_completion=False,
)
pipeline_app = typer.Typer(help="First-class pipeline helpers over the member CLIs")
app.add_typer(pipeline_app, name="pipeline")
console = Console()
err = Console(stderr=True)


@dataclass
class RuntimeOverrides:
    provider: str | None = None
    model: str | None = None


_OVERRIDES = RuntimeOverrides()


@app.callback()
def main(
    provider: Annotated[
        str | None,
        typer.Option(
            "--provider",
            help="Forwarded as LLM_PROVIDER to member CLIs that support it",
        ),
    ] = None,
    model: Annotated[
        str | None,
        typer.Option(
            "--model",
            help="Forwarded as CLAUDE_MODEL to member CLIs that support it",
        ),
    ] = None,
) -> None:
    _OVERRIDES.provider = provider.strip() if provider else None
    _OVERRIDES.model = model.strip() if model else None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return utc_now_iso()


def _subprocess_env() -> dict[str, str]:
    env = os.environ.copy()
    if _OVERRIDES.provider:
        env["LLM_PROVIDER"] = _OVERRIDES.provider
    if _OVERRIDES.model:
        env["CLAUDE_MODEL"] = _OVERRIDES.model
    return env


def _run(bin_name: str, args: list[str]) -> None:
    """Resolve bin, exec, forward exit code."""
    resolved = shutil.which(bin_name)
    if not resolved:
        err.print(f"[red]error:[/red] '{bin_name}' not found — run: uv sync --group dev")
        raise typer.Exit(2)
    result = subprocess.run([resolved, *args], env=_subprocess_env())
    raise typer.Exit(result.returncode)


def _capture_json(command: list[str]) -> dict[str, Any]:
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )
    if result.returncode != 0:
        message = (result.stderr or result.stdout or "subprocess failed").strip()
        raise RuntimeError(message)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Command did not return JSON: {' '.join(command)}") from exc


def _resolve_bin(bin_name: str) -> str:
    resolved = shutil.which(bin_name)
    if not resolved:
        raise RuntimeError(f"'{bin_name}' not found — run: uv sync --group dev")
    return resolved


def _capture_member_json(bin_name: str, args: list[str]) -> dict[str, Any]:
    return _capture_json([_resolve_bin(bin_name), *args])


def _studio_bin() -> str | None:
    """Resolve the Studio entry point.

    Priority:
    1. agentcy-studio in PATH (global install)
    2. studio/bin/studio.js relative to monorepo root (local dev)
    """
    if found := shutil.which("agentcy-studio"):
        return found
    root = Path(__file__).resolve().parent.parent
    local = root / "studio" / "bin" / "studio.js"
    if local.exists():
        return str(local)
    return None


def _studio_command(args: list[str]) -> list[str]:
    node = shutil.which("node")
    if not node:
        err.print("[red]error:[/red] 'node' not found — install Node.js")
        raise typer.Exit(2)

    bin_path = _studio_bin()
    if not bin_path:
        err.print("[red]error:[/red] studio not found — run: cd studio && pnpm install")
        raise typer.Exit(2)

    if bin_path.endswith(".js"):
        return [node, bin_path, *args]
    return [bin_path, *args]


def _capture_studio_json(args: list[str]) -> dict[str, Any]:
    return _capture_json(_studio_command(args))


def _run_node(args: list[str]) -> None:
    result = subprocess.run(_studio_command(args), env=_subprocess_env())
    raise typer.Exit(result.returncode)


def _member_specs() -> dict[str, tuple[str, str]]:
    return {
        "voice": ("agentcy-voice", "global"),
        "briefs": ("agentcy-briefs", "global"),
        "forecast": ("agentcy-forecast", "subcommand"),
        "studio": ("agentcy-studio", "global"),
        "measure": ("agentcy-measure", "global"),
    }


def _normalize_member_name(member: str) -> str:
    normalized = member.strip().lower()
    if normalized not in _member_specs():
        raise typer.BadParameter(
            "member must be one of: " + ", ".join(sorted(_member_specs()))
        )
    return normalized


def _inject_member_json(member: str, args: list[str]) -> tuple[list[str], bool]:
    if "--json" in args:
        return list(args), False
    _, json_style = _member_specs()[member]
    if json_style == "global":
        return ["--json", *args], True
    if member == "forecast":
        if not args:
            return list(args), False
        if args[0] in {"doctor", "run"}:
            return [*args, "--json"], True
        if args[0] == "runs" and len(args) > 1 and args[1] in {"list", "status", "export"}:
            return [*args, "--json"], True
    return list(args), False


def _member_command(member: str, args: list[str]) -> list[str]:
    if member == "studio":
        return _studio_command(args)
    bin_name, _ = _member_specs()[member]
    return [_resolve_bin(bin_name), *args]


def _parse_member_output(stdout: str) -> tuple[Any, str]:
    text = stdout.strip()
    if not text:
        return None, "empty"
    try:
        return json.loads(text), "json"
    except json.JSONDecodeError:
        return text, "text"


def _normalize_member_payload(payload: Any) -> dict[str, Any]:
    """Normalize a member's stdout into the canonical envelope shape.

    Members that already emit ``{status, command, data}`` pass through.
    Members that emit raw data are wrapped as ``ok`` with the raw payload as ``result``.
    """
    normalized = {
        "member_status": "ok",
        "member_command": None,
        "result": payload,
        "error": None,
    }
    if isinstance(payload, dict) and payload.get("status") in {"ok", "error"}:
        normalized["member_status"] = payload["status"]
        normalized["member_command"] = payload.get("command")
        normalized["result"] = payload.get("data")
        normalized["error"] = payload.get("error")
    return normalized


def _run_member_enveloped(member: str, args: list[str]) -> tuple[dict[str, Any], int]:
    member = _normalize_member_name(member)
    command_args, injected_json = _inject_member_json(member, args)
    command = _member_command(member, command_args)
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        env=_subprocess_env(),
    )
    parsed_output, result_format = _parse_member_output(result.stdout)
    normalized = _normalize_member_payload(parsed_output)
    stderr_text = result.stderr.strip() or None
    payload = {
        "member": member,
        "argv": args,
        "exit_code": result.returncode,
        "json_invoked": injected_json or "--json" in command_args,
        "result_format": result_format,
        "member_status": normalized["member_status"],
        "member_command": normalized["member_command"],
        "result": normalized["result"],
    }
    if stderr_text:
        payload["stderr"] = stderr_text
    if normalized["error"] is not None:
        payload["error"] = normalized["error"]

    ok = result.returncode == 0 and normalized["member_status"] != "error"
    envelope = _envelope(payload, command="member")
    if not ok:
        envelope["status"] = "error"
    return envelope, (0 if ok else result.returncode or 1)


def _probe_member(command: list[str]) -> bool:
    result = subprocess.run(
        command,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
        env=_subprocess_env(),
    )
    return result.returncode == 0


def _capture_optional_json(command: list[str]) -> dict[str, Any] | None:
    try:
        return _capture_json(command)
    except RuntimeError:
        return None


def _install_profiles() -> dict[str, dict[str, Any]]:
    return {
        "python-suite": {
            "summary": (
                "Base Python workspace for protocols, voice, briefs, forecast, measure, "
                "and root CLI."
            ),
            "commands": ["uv sync --group dev"],
            "includes": [
                "agentcy root dispatcher",
                "protocols",
                "voice",
                "briefs",
                "forecast base CLI",
                "measure",
            ],
            "excludes": ["forecast simulation environment", "studio runtime"],
        },
        "forecast-simulation": {
            "summary": "Create the isolated Python 3.11 environment for full Forecast simulation.",
            "commands": ["make install-forecast-simulation"],
            "includes": [
                "forecast/.venv-simulation",
                "camel-oasis and camel-ai pinned for agentcy-forecast full runs",
            ],
            "excludes": ["base Python workspace", "studio runtime"],
        },
        "studio-runtime": {
            "summary": "Install the Node runtime needed for agentcy-studio.",
            "commands": ["cd studio && pnpm install"],
            "includes": ["agentcy-studio runtime", "studio tests/typecheck"],
            "excludes": [],
        },
        "full-operator": {
            "summary": "Install the full operator stack for end-to-end local pipeline runs.",
            "commands": [
                "uv sync --group dev",
                "make install-forecast-simulation",
                "cd studio && pnpm install",
            ],
            "includes": [
                "all Python members",
                "forecast full simulation runtime in forecast/.venv-simulation",
                "studio runtime",
            ],
            "excludes": [],
        },
    }


def _foundation_payload() -> dict[str, dict[str, Any]]:
    return {
        "brand": {
            "purpose": "Canonical brand identity, audience, offers, proof, rules, and constraints.",
            "primary_sources": [
                "brands/<brand>/BRAND.md",
                "brands/<brand>/brand.yml",
            ],
            "consumed_by": ["briefs", "studio", "forecast"],
        },
        "voice": {
            "purpose": "Persona, tone, behavioral boundaries, examples, and voice drift evidence.",
            "primary_artifact": "voice_pack.v1",
            "owner": "voice",
            "consumed_by": ["briefs", "studio", "measure"],
        },
        "visual": {
            "purpose": "Palette, typography, logo references, image style, and composition rules.",
            "primary_sources": [
                "brands/<brand>/BRAND.md",
                "brands/<brand>/DESIGN.md",
                "brands/<brand>/assets/",
            ],
            "consumed_by": ["studio"],
        },
        "content": {
            "purpose": "Signals, pillars, campaign intent, proof, CTA, channel guidance, and risks.",
            "primary_artifact": "brief.v1",
            "owner": "briefs",
            "consumed_by": ["forecast", "studio", "measure"],
        },
        "outcomes": {
            "purpose": "Published results, measured performance, calibration, and study output.",
            "primary_artifacts": ["run_result.v1", "performance.v1"],
            "owners": ["studio", "measure"],
            "consumed_by": ["voice", "briefs"],
        },
    }


def _extension_model_payload() -> dict[str, Any]:
    return {
        "principle": (
            "Extensions turn the same brand, voice, visual, and content foundation into "
            "specific channel artifacts; they should not invent a separate product core."
        ),
        "extension_contract": [
            "declares foundation inputs",
            "declares owned output artifact or sidecar",
            "names the runtime owner",
            "uses deterministic local composition when exact brand rendering matters",
            "ships fixture or smoke verification",
        ],
        "families": {
            "studio-generation": {
                "owner": "studio",
                "current": ["social.post", "blog.post", "outreach.touch", "respond.reply"],
                "next": [
                    "og.cover",
                    "social.card",
                    "carousel",
                    "short.video",
                    "ugc.ad",
                    "longform.script",
                    "campaign.pack",
                ],
            },
            "forecasting": {
                "owner": "forecast",
                "current": ["audience reaction forecast", "repo-local run_eval sidecar"],
                "next": ["objection lanes", "message risk forecast", "creative variant forecast"],
            },
            "measurement": {
                "owner": "measure",
                "current": ["adapt", "calibrate", "study"],
                "next": ["channel benchmarks", "voice drift feedback", "creative pattern memory"],
            },
            "agent-instructions": {
                "owner": "skills/agentcy",
                "current": ["repo-local Agentcy skill with reference files"],
                "next": ["mode-specific reference packs for generation and video workflows"],
            },
        },
    }


def _suite_catalog_payload() -> dict[str, Any]:
    from agentcy import __version__

    return {
        "suite": {
            "name": "agentcy",
            "version": __version__,
            "positioning": (
                "Agent-native brand and content stack: one foundation, many "
                "artifact-producing extensions"
            ),
            "drop_in_package": False,
            "consumption_model": [
                "agentcy skills as the agent instruction layer",
                "brand, voice, visual, and content as the durable foundation",
                "agentcy-protocols as the schema and handoff layer",
                "functional agentcy-* CLIs as stage-owned runtimes",
                "agentcy as the umbrella dispatcher and pipeline orchestrator",
            ],
            "best_use_cases": [
                "voice -> briefs -> forecast -> studio -> measure pipelines",
                "AI-native operator workflows that need resumable artifact handoffs",
                "human-and-agent collaboration over stable JSON/file contracts",
            ],
            "not_best_for": [
                "single import-and-go SDK embedding",
                "non-technical users who need one-click SaaS onboarding",
            ],
        },
        "foundation": _foundation_payload(),
        "extension_model": _extension_model_payload(),
        "install_profiles": _install_profiles(),
        "members": {
            "protocols": {
                "package": "agentcy-protocols",
                "bin": None,
                "dispatcher": None,
                "runtime": "python",
                "owns_artifact": "schemas + adapters only",
                "json_contract": "library layer, not an operator CLI",
                "purpose": "Shared schemas, examples, and adapters",
            },
            "voice": {
                "package": "agentcy-voice",
                "bin": "agentcy-voice",
                "dispatcher": "agentcy voice",
                "runtime": "python",
                "owns_artifact": "voice_pack.v1",
                "json_contract": "global --json",
                "purpose": "Voice/persona management and voice-pack export",
            },
            "briefs": {
                "package": "agentcy-briefs",
                "bin": "agentcy-briefs",
                "dispatcher": "agentcy briefs",
                "runtime": "python",
                "owns_artifact": "brief.v1",
                "json_contract": "mixed surfaces; prefer documented command forms such as -f json",
                "purpose": "Strategy, planning, and brief writing",
            },
            "forecast": {
                "package": "agentcy-forecast",
                "bin": "agentcy-forecast",
                "dispatcher": "agentcy forecast",
                "runtime": "python",
                "owns_artifact": "forecast.v1",
                "json_contract": "subcommand-level --json",
                "purpose": "Scenario simulation and forecast generation",
            },
            "studio": {
                "package": "agentcy-studio",
                "bin": "agentcy-studio",
                "dispatcher": "agentcy studio",
                "runtime": "node",
                "owns_artifact": "run_result.v1",
                "json_contract": "subcommand-level --json",
                "purpose": "Creative/content generation, review, and publish runtime",
            },
            "measure": {
                "package": "agentcy-measure",
                "bin": "agentcy-measure",
                "dispatcher": "agentcy measure",
                "runtime": "python",
                "owns_artifact": "performance.v1",
                "json_contract": "top-level --json with normalized envelope",
                "purpose": "Measurement, calibration, and repo-local study synthesis",
            },
        },
    }


def _print_quickstart(profile: str, data: dict[str, Any]) -> None:
    console.print(f"[bold]agentcy quickstart[/bold] — {profile}")
    console.print(data["summary"])
    console.print("\n[bold]Commands[/bold]")
    for command in data["commands"]:
        console.print(f"  {command}")
    if data.get("includes"):
        console.print("\n[bold]Includes[/bold]")
        for item in data["includes"]:
            console.print(f"  - {item}")
    if data.get("excludes"):
        console.print("\n[bold]Still separate[/bold]")
        for item in data["excludes"]:
            console.print(f"  - {item}")




# ---------------------------------------------------------------------------
# Subcommands — each is a transparent pass-through
# ---------------------------------------------------------------------------

_PASS = {"allow_extra_args": True, "ignore_unknown_options": True}


@app.command(
    "voice",
    context_settings=_PASS,
    help="Voice/persona management — create, test, optimize, export",
)
def voice(ctx: typer.Context) -> None:
    _run("agentcy-voice", ctx.args)


@app.command(
    "briefs",
    context_settings=_PASS,
    help="Brand strategy and brief writing",
)
def briefs(ctx: typer.Context) -> None:
    _run("agentcy-briefs", ctx.args)


@app.command(
    "forecast",
    context_settings=_PASS,
    help="Audience/social forecasting — docs + requirement -> forecast",
)
def forecast(ctx: typer.Context) -> None:
    _run("agentcy-forecast", ctx.args)


@app.command(
    "studio",
    context_settings=_PASS,
    help="Creative studio — brief -> draft -> render -> review -> publish",
)
def studio(ctx: typer.Context) -> None:
    _run_node(ctx.args)


@app.command(
    "measure",
    context_settings=_PASS,
    help="Measurement + calibration — run_result -> performance",
)
def measure(ctx: typer.Context) -> None:
    _run("agentcy-measure", ctx.args)


@app.command(
    "member",
    context_settings=_PASS,
    help="Run a member CLI behind a normalized envelope when --json is set.",
)
def member(
    member: Annotated[str, typer.Argument(help="voice | briefs | forecast | studio | measure")],
    ctx: typer.Context,
    json_out: Annotated[
        bool,
        typer.Option("--json", help="Emit a normalized JSON envelope"),
    ] = False,
) -> None:
    member = _normalize_member_name(member)
    if not json_out:
        if member == "studio":
            _run_node(ctx.args)
        bin_name, _ = _member_specs()[member]
        _run(bin_name, ctx.args)

    envelope, exit_code = _run_member_enveloped(member, ctx.args)
    print(json.dumps(envelope, indent=2))
    raise typer.Exit(exit_code)


# ---------------------------------------------------------------------------
# pipeline — first-class orchestration helpers
# ---------------------------------------------------------------------------



@app.command("catalog")
def catalog(
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False,
) -> None:
    """Describe the suite, member ownership, and install profiles."""
    payload = _suite_catalog_payload()
    if json_out:
        print(json.dumps(_envelope(payload, command="catalog"), indent=2))
        raise typer.Exit(0)

    table = Table(title="agentcy catalog")
    table.add_column("member")
    table.add_column("artifact")
    table.add_column("runtime")
    table.add_column("json")
    for name, info in payload["members"].items():
        table.add_row(name, info["owns_artifact"], info["runtime"], info["json_contract"])
    console.print(table)
    console.print(
        "\n[bold]Best fit:[/bold] "
        + "; ".join(payload["suite"]["best_use_cases"])
    )
    console.print(
        "[bold]Packaging:[/bold] umbrella CLI + member CLIs + protocols library; "
        "not a single drop-in SDK"
    )
    raise typer.Exit(0)


@app.command("quickstart")
def quickstart(
    profile: Annotated[
        str,
        typer.Option(
            "--profile",
            help="Install profile: python-suite | forecast-simulation | studio-runtime | full-operator",
        ),
    ] = "python-suite",
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False,
) -> None:
    """Print the smallest install path for a given suite profile."""
    profiles = _install_profiles()
    if profile not in profiles:
        raise typer.BadParameter(
            "--profile must be one of: " + ", ".join(sorted(profiles))
        )
    payload = {"profile": profile, **profiles[profile]}
    if json_out:
        print(json.dumps(_envelope(payload, command="quickstart"), indent=2))
        raise typer.Exit(0)

    _print_quickstart(profile, payload)
    raise typer.Exit(0)


@app.command("doctor")
def doctor(
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False,
) -> None:
    """Check that all member CLIs are installed and healthy."""
    node = shutil.which("node")
    claude = shutil.which("claude")
    members = [
        ("voice", "agentcy-voice", "python", ["agentcy-voice", "--version"]),
        ("briefs", "agentcy-briefs", "python", ["agentcy-briefs", "--help"]),
        ("forecast", "agentcy-forecast", "python", ["agentcy-forecast", "doctor", "--json"]),
        ("studio", "agentcy-studio", "node", None),
        ("measure", "agentcy-measure", "python", ["agentcy-measure", "doctor", "--json"]),
    ]

    results: dict[str, dict[str, Any]] = {}
    all_ok = True

    for name, bin_name, runtime, probe_command in members:
        details = None
        if runtime == "node":
            resolved = _studio_bin()
            found = resolved is not None and node is not None
            reachable = found and _probe_member(_studio_command(["help", "--json"]))
        else:
            resolved = shutil.which(bin_name)
            found = resolved is not None
            reachable = False
            if found and probe_command is not None:
                if probe_command[-1] == "--json":
                    details = _capture_optional_json([resolved, *probe_command[1:]])
                    reachable = details is not None
                else:
                    reachable = _probe_member([resolved, *probe_command[1:]])
        if not found or not reachable:
            all_ok = False
        results[name] = {
            "bin": bin_name,
            "found": found,
            "reachable": reachable,
            "runtime": runtime,
            "details": details,
        }

    results["_env"] = {
        "python": sys.version.split()[0],
        "node": node is not None,
        "claude": claude is not None,
        "provider": _OVERRIDES.provider,
        "model": _OVERRIDES.model,
    }

    if json_out:
        doctor_envelope = _envelope(results, command="doctor")
        if not all_ok:
            doctor_envelope["status"] = "error"
        print(json.dumps(doctor_envelope))
        raise typer.Exit(0 if all_ok else 1)

    table = Table(title="agentcy doctor")
    table.add_column("member")
    table.add_column("bin")
    table.add_column("status")
    for name, info in results.items():
        if name == "_env":
            continue
        if not info["found"]:
            status = "[red]missing[/red]"
        elif info["reachable"]:
            status = "[green]ok[/green]"
        else:
            status = "[yellow]broken[/yellow]"
        table.add_row(name, info["bin"], status)
    console.print(table)
    raise typer.Exit(0 if all_ok else 1)


# ---------------------------------------------------------------------------
# version
# ---------------------------------------------------------------------------


@app.command("version")
def version() -> None:
    """Print suite version."""
    from agentcy import __version__

    console.print(f"agentcy {__version__}")


# Register pipeline subcommands (must be after all shared helpers defined above).
from agentcy import pipeline as _pipeline  # noqa: E402, F401
