"""agentcy — agent CLI suite.

Pipeline:
    agentcy persona --json export <persona> --to voice-pack.v1
    agentcy brand plan run "<brief>" --brand <id> --json
    agentcy forecast run --files docs/ --brief brief.v1.json --json
    agentcy studio run social.post --brand <id> --json
    agentcy metrics adapt --run-result run.json --sidecar s.json --json
    agentcy metrics calibrate --forecast f.json --performance p.json
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(
    name="agentcy",
    help="Agent CLI suite — persona | brand | forecast | studio | metrics",
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
    return datetime.now(UTC).isoformat()


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
        err.print(f"[red]error:[/red] '{bin_name}' not found — run: uv sync --all-extras")
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
        raise RuntimeError(f"'{bin_name}' not found — run: uv sync --all-extras")
    return resolved


def _capture_member_json(bin_name: str, args: list[str]) -> dict[str, Any]:
    return _capture_json([_resolve_bin(bin_name), *args])


def _loom_bin() -> str | None:
    """Resolve the studio (loom) entry point."""
    if found := shutil.which("agentcy studio"):
        return found
    root = Path(__file__).parent.parent.parent
    local = root / "studio" / "runtime" / "bin" / "loom.js"
    if local.exists():
        return str(local)
    return None


def _loom_command(args: list[str]) -> list[str]:
    node = shutil.which("node")
    if not node:
        err.print("[red]error:[/red] 'node' not found — install Node.js")
        raise typer.Exit(2)

    bin_path = _loom_bin()
    if not bin_path:
        err.print("[red]error:[/red] studio not found — run: cd studio/runtime && pnpm install")
        raise typer.Exit(2)

    if bin_path.endswith(".js"):
        return [node, bin_path, *args]
    return [bin_path, *args]


def _capture_loom_json(args: list[str]) -> dict[str, Any]:
    return _capture_json(_loom_command(args))


def _run_node(args: list[str]) -> None:
    result = subprocess.run(_loom_command(args), env=_subprocess_env())
    raise typer.Exit(result.returncode)


def _member_specs() -> dict[str, tuple[str, str]]:
    return {
        "persona": ("agentcy persona", "global"),
        "brand": ("agentcy brand", "global"),
        "forecast": ("agentcy forecast", "subcommand"),
        "studio": ("agentcy studio", "global"),
        "metrics": ("agentcy metrics", "global"),
    }


def _normalize_member_name(member: str) -> str:
    normalized = member.strip().lower()
    if normalized not in _member_specs():
        raise typer.BadParameter(
            "member must be one of: " + ", ".join(sorted(_member_specs()))
        )
    return normalized


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


def _pipeline_root(output_dir: Path | None) -> Path:
    return (output_dir or Path("artifacts") / "pipelines").resolve()


def _pipeline_manifest_path(output_dir: Path | None, pipeline_id: str) -> Path:
    return _pipeline_root(output_dir) / pipeline_id / "manifest.json"


def _write_json(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _save_pipeline_manifest(path: Path, payload: dict[str, Any]) -> Path:
    payload = dict(payload)
    payload["updated_at"] = _utc_now()
    return _write_json(path, payload)


def _safe_slug(value: str) -> str:
    return "-".join(part for part in value.strip().lower().replace("_", "-").split("-") if part)


def _canonical_brand_id(brand: str, explicit: str | None = None) -> str:
    if explicit and explicit.strip():
        return explicit.strip()
    return f"{_safe_slug(brand)}.brand.core"


def _module_dir(pipeline_dir: Path, module: str) -> Path:
    path = pipeline_dir / module
    path.mkdir(parents=True, exist_ok=True)
    return path


def _copy_json_file(source: Path, destination: Path) -> Path:
    payload = _load_json(source)
    return _write_json(destination, payload)


def _record_degradation(manifest: dict[str, Any], message: str) -> dict[str, Any]:
    degradations = list(manifest.get("degradations") or [])
    if message not in degradations:
        degradations.append(message)
    manifest["degradations"] = degradations
    return manifest


def _read_json_if_exists(path: str | Path | None) -> dict[str, Any] | None:
    if path is None:
        return None
    candidate = Path(path)
    if not candidate.exists():
        return None
    return _load_json(candidate)


def _install_profiles() -> dict[str, dict[str, Any]]:
    return {
        "python-suite": {
            "summary": (
                "Base Python workspace for protocols, vox, compass, echo, pulse, "
                "and root CLI."
            ),
            "commands": ["uv sync --group dev"],
            "includes": [
                "agentcy root dispatcher",
                "protocols",
                "vox",
                "compass",
                "echo base CLI",
                "pulse",
            ],
            "excludes": ["echo simulation extra", "loom runtime"],
        },
        "echo-simulation": {
            "summary": "Add the full Echo simulation runtime on Python 3.11.",
            "commands": ["uv sync --extra simulation"],
            "includes": ["camel-oasis runtime for agentcy forecast full runs"],
            "excludes": ["loom runtime"],
        },
        "loom-runtime": {
            "summary": "Install the Node runtime needed for agentcy studio.",
            "commands": ["cd loom/runtime && pnpm install"],
            "includes": ["agentcy studio runtime", "loom tests/typecheck"],
            "excludes": [],
        },
        "full-operator": {
            "summary": "Install the full operator stack for end-to-end local pipeline runs.",
            "commands": [
                "uv sync --group dev",
                "uv sync --extra simulation",
                "cd loom/runtime && pnpm install",
            ],
            "includes": [
                "all Python members",
                "echo full simulation runtime",
                "loom runtime",
            ],
            "excludes": [],
        },
    }


def _suite_catalog_payload() -> dict[str, Any]:
    from agentcy import __version__

    return {
        "suite": {
            "name": "agentcy",
            "version": __version__,
            "positioning": "Protocol-first suite of stage-owned workflow CLIs",
            "drop_in_package": False,
            "consumption_model": [
                "agentcy-protocols as the library/schema layer",
                "agentcy-* member CLIs as stage-owned workflow tools",
                "agentcy as the umbrella dispatcher and pipeline orchestrator",
            ],
            "best_use_cases": [
                "persona -> brief -> forecast -> execution -> measurement pipelines",
                "AI-native operator workflows that need resumable artifact handoffs",
                "human-and-agent collaboration over stable JSON/file contracts",
            ],
            "not_best_for": [
                "single import-and-go SDK embedding",
                "non-technical users who need one-click SaaS onboarding",
            ],
        },
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
            "vox": {
                "package": "agentcy persona",
                "bin": "agentcy persona",
                "dispatcher": "agentcy vox",
                "runtime": "python",
                "owns_artifact": "voice_pack.v1",
                "json_contract": "global --json",
                "purpose": "Persona management and voice-pack export",
            },
            "compass": {
                "package": "agentcy brand",
                "bin": "agentcy brand",
                "dispatcher": "agentcy compass",
                "runtime": "python",
                "owns_artifact": "brief.v1",
                "json_contract": "mixed surfaces; prefer documented command forms such as -f json",
                "purpose": "Strategy, planning, and brief writing",
            },
            "echo": {
                "package": "agentcy forecast",
                "bin": "agentcy forecast",
                "dispatcher": "agentcy echo",
                "runtime": "python",
                "owns_artifact": "forecast.v1",
                "json_contract": "subcommand-level --json",
                "purpose": "Scenario simulation and forecast generation",
            },
            "loom": {
                "package": "agentcy studio",
                "bin": "agentcy studio",
                "dispatcher": "agentcy loom",
                "runtime": "node",
                "owns_artifact": "run_result.v1",
                "json_contract": "subcommand-level --json",
                "purpose": "Execution, review, and publish runtime",
            },
            "pulse": {
                "package": "agentcy metrics",
                "bin": "agentcy metrics",
                "dispatcher": "agentcy pulse",
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


def _select_loom_variant(loom_inspect: dict[str, Any] | None) -> dict[str, Any] | None:
    if not loom_inspect:
        return None
    data = dict(loom_inspect.get("data") or {})
    for artifact in data.get("artifacts") or []:
        if artifact.get("type") != "draft_set":
            continue
        variants = ((artifact.get("data") or {}).get("variants") or [])
        if variants:
            return variants[0]
    return None


def _write_operator_report(pipeline_dir: Path, manifest: dict[str, Any]) -> Path:
    artifacts = dict(manifest.get("artifacts") or {})
    echo_eval = _read_json_if_exists(artifacts.get("echo_run_eval"))
    forecast = _read_json_if_exists(artifacts.get("forecast"))
    pulse_study = _read_json_if_exists(artifacts.get("study"))
    loom_inspect = _read_json_if_exists(artifacts.get("loom_inspect"))
    best_variant = _select_loom_variant(loom_inspect)

    lines = [
        f"# Pipeline report — {manifest.get('pipeline_id', 'unknown')}",
        "",
        "## Status",
        "",
        f"- Mode: {manifest.get('mode', 'preview')}",
        f"- Brand: {manifest.get('brand')}",
        f"- Brand ID: {manifest.get('brand_id')}",
        f"- Persona: {manifest.get('persona')}",
    ]

    if manifest.get("degradations"):
        lines.extend(["", "## Degradations", ""])
        lines.extend(f"- {item}" for item in manifest["degradations"])

    if forecast:
        summary = dict(forecast.get("summary") or {})
        lines.extend([
            "",
            "## Forecast",
            "",
            f"- Thesis: {summary.get('thesis', 'n/a')}",
            f"- Confidence: {summary.get('confidence', 'n/a')}",
        ])

    if echo_eval:
        summary = dict(echo_eval.get("summary") or {})
        metrics = dict(echo_eval.get("metrics") or {})
        lines.extend([
            "",
            "## Echo run eval",
            "",
            f"- Activity pattern: {summary.get('activity_pattern', 'n/a')}",
            f"- Coverage note: {summary.get('coverage_note', 'n/a')}",
            f"- Total actions: {metrics.get('total_actions', 'n/a')}",
        ])

    if best_variant:
        lines.extend([
            "",
            "## Best draft",
            "",
            f"- Hook: {best_variant.get('hook', 'n/a')}",
            f"- Body: {best_variant.get('body', 'n/a')}",
            f"- CTA: {best_variant.get('cta', 'n/a')}",
        ])

    if pulse_study:
        lines.extend([
            "",
            "## Pulse study",
            "",
            f"- Verdict: {pulse_study.get('study_verdict', 'n/a')}",
            f"- Recommendation: {pulse_study.get('recommendation', 'n/a')}",
        ])
    elif artifacts.get("pulse_preview"):
        preview = _read_json_if_exists(artifacts.get("pulse_preview")) or {}
        lines.extend([
            "",
            "## Pulse",
            "",
            f"- Status: {preview.get('status', 'skipped')}",
            "- Note: "
            + preview.get(
                "reason",
                "preview mode does not emit canonical performance.v1",
            ),
        ])

    report_path = _module_dir(pipeline_dir, "reports") / "operator_report.md"
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def _finalize_pipeline_bundle(
    manifest_path: Path,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    pipeline_dir = manifest_path.parent
    report_path = _write_operator_report(pipeline_dir, manifest)
    manifest = _record_pipeline_artifact(manifest, "operator_report", str(report_path))
    bundle_path = pipeline_dir / "bundle_manifest.json"
    _write_json(bundle_path, manifest)
    manifest = _record_pipeline_artifact(manifest, "bundle_manifest", str(bundle_path))
    _save_pipeline_manifest(manifest_path, manifest)
    _write_json(bundle_path, manifest)
    return manifest


def _default_pipeline_manifest(
    pipeline_id: str,
    *,
    persona: str,
    brand: str,
    brand_id: str,
    brief: str,
    files: list[str],
    smoke: bool,
    mode: str,
    persona_eval: bool,
    loom_workflow: str | None,
) -> dict[str, Any]:
    return {
        "pipeline_id": pipeline_id,
        "created_at": _utc_now(),
        "updated_at": _utc_now(),
        "persona": persona,
        "brand": brand,
        "brand_id": brand_id,
        "brief": brief,
        "files": files,
        "smoke": smoke,
        "mode": mode,
        "persona_eval": persona_eval,
        "loom_workflow": loom_workflow,
        "llm": {
            "provider": _OVERRIDES.provider,
            "model": _OVERRIDES.model,
        },
        "steps": {},
        "artifacts": {},
        "degradations": [],
    }


def _record_pipeline_step(
    manifest: dict[str, Any],
    step: str,
    *,
    status: str,
    data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    steps = dict(manifest.get("steps") or {})
    steps[step] = {
        "status": status,
        "updated_at": _utc_now(),
        "data": data or {},
    }
    manifest["steps"] = steps
    return manifest


def _record_pipeline_artifact(
    manifest: dict[str, Any],
    key: str,
    value: str | None,
) -> dict[str, Any]:
    if not value:
        return manifest
    artifacts = dict(manifest.get("artifacts") or {})
    artifacts[key] = value
    manifest["artifacts"] = artifacts
    return manifest


def _loom_review_publish(
    manifest: dict[str, Any],
    loom_run_id: str,
    loom_dir: Path,
    *,
    dry_run: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Review + publish a loom run. Returns (manifest, publish_payload, run_result)."""
    review_payload = _loom_envelope_data(
        _capture_loom_json(["review", "approve", loom_run_id, "--json"])
    )
    review_path = loom_dir / "review.json"
    _write_json(review_path, review_payload)
    manifest = _record_pipeline_artifact(manifest, "loom_review", str(review_path))

    publish_cmd = ["publish", loom_run_id, "--dry-run", "--json"] if dry_run else [
        "publish", loom_run_id, "--json"
    ]
    publish_payload = _loom_envelope_data(_capture_loom_json(publish_cmd))
    publish_path = loom_dir / "publish.json"
    _write_json(publish_path, publish_payload)
    manifest = _record_pipeline_artifact(manifest, "loom_publish", str(publish_path))

    run_result = dict(publish_payload.get("runResult") or {})
    if run_result:
        run_result_path = loom_dir / "run_result.v1.json"
        _write_json(run_result_path, run_result)
        manifest = _record_pipeline_artifact(manifest, "run_result", str(run_result_path))

    return manifest, publish_payload, run_result


def _echo_artifacts_for_run(run_id: str, output_dir: str | None) -> dict[str, Any]:
    args = ["runs", "export", run_id, "--json"]
    if output_dir:
        args.extend(["--output-dir", output_dir])
    return _capture_member_json("agentcy forecast", args)


def _pulse_envelope_data(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("data") or payload)


def _loom_envelope_data(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("data") or payload)


def _run_compass_plan(
    command: list[str],
    *,
    provider: str | None = None,
    cwd: Path | None = None,
) -> tuple[str, bool]:
    supported = {"mock", "gemini", "anthropic", "claude-cli"}
    preferred = (
        provider
        or os.environ.get("BRANDOPS_LLM_PROVIDER")
        or _OVERRIDES.provider
        or os.environ.get("LLM_PROVIDER")
        or "gemini"
    ).strip()
    if preferred not in supported:
        preferred = "gemini"

    tried: list[str] = []
    for candidate in [preferred, *(["mock"] if preferred != "mock" else [])]:
        tried.append(candidate)
        env = _subprocess_env()
        env["BRANDOPS_LLM_PROVIDER"] = candidate
        model = os.environ.get("BRANDOPS_LLM_MODEL") or _OVERRIDES.model or os.environ.get(
            "CLAUDE_MODEL"
        )
        if model:
            env.setdefault("BRANDOPS_LLM_MODEL", model)
        try:
            subprocess.run(
                command,
                capture_output=True,
                text=True,
                env=env,
                check=True,
                cwd=str(cwd) if cwd is not None else None,
            )
            return candidate, candidate != preferred
        except subprocess.CalledProcessError as exc:
            if candidate == "mock" or preferred == "mock":
                message = (exc.stderr or exc.stdout or str(exc)).strip()
                raise RuntimeError(message) from exc
    raise RuntimeError(f"Compass failed for providers: {', '.join(tried)}")


# ---------------------------------------------------------------------------
# Subcommands — direct imports for Python, subprocess for TypeScript (loom)
# ---------------------------------------------------------------------------

from agentcy.persona.cli import app as persona_app
from agentcy.brand.cli import app as brand_app

app.add_typer(persona_app, name="persona", help="Persona management — create, test, optimize, export")
app.add_typer(brand_app, name="brand", help="Brand ops — signals, planning, production, loop")

_PASS = {"allow_extra_args": True, "ignore_unknown_options": True}


@app.command("forecast", context_settings=_PASS, help="Swarm prediction — docs + requirement → forecast")
def forecast(ctx: typer.Context) -> None:
    from agentcy.forecast.cli import main as forecast_main
    raise typer.Exit(forecast_main(ctx.args))


@app.command("studio", context_settings=_PASS, help="Content studio — draft, render, publish")
def studio(ctx: typer.Context) -> None:
    _run_node(ctx.args)


@app.command("metrics", context_settings=_PASS, help="Measurement + calibration — run_result → performance")
def metrics(ctx: typer.Context) -> None:
    from agentcy.metrics.cli import main as metrics_main
    raise typer.Exit(metrics_main(ctx.args))


# ---------------------------------------------------------------------------
# pipeline — first-class orchestration helpers
# ---------------------------------------------------------------------------


@pipeline_app.command("run")
def pipeline_run(
    persona: Annotated[
        str,
        typer.Option("--persona", help="Persona name to export via agentcy persona"),
    ],
    brand: Annotated[str, typer.Option("--brand", help="Brand name for compass/loom")],
    brief: Annotated[str, typer.Option("--brief", help="Campaign brief text")],
    files: Annotated[list[Path], typer.Option("--files", help="Source files for echo")],
    smoke: Annotated[bool, typer.Option("--smoke", help="Use echo smoke mode")]=False,
    mode: Annotated[
        str,
        typer.Option("--mode", help="Pipeline mode: preview or live"),
    ] = "preview",
    brand_id: Annotated[
        str | None,
        typer.Option("--brand-id", help="Canonical brand lineage ID override"),
    ] = None,
    compass_provider: Annotated[
        str | None,
        typer.Option("--compass-provider", help="Preferred Compass LLM provider"),
    ] = None,
    persona_eval: Annotated[
        bool,
        typer.Option("--persona-eval", help="Run and save a stress eval before export"),
    ] = False,
    loom_workflow: Annotated[
        str | None,
        typer.Option(
            "--loom-workflow",
            help="Optionally start a loom workflow with the generated brief",
        ),
    ] = None,
    allow_live_publish: Annotated[
        bool,
        typer.Option(
            "--allow-live-publish",
            help="Required to let --mode live publish beyond a dry run",
        ),
    ] = False,
    pipeline_id: Annotated[
        str | None,
        typer.Option("--pipeline-id", help="Named pipeline folder under the output root"),
    ] = None,
    output_dir: Annotated[
        Path | None,
        typer.Option("--output-dir", help="Pipeline manifest/output root"),
    ] = None,
    echo_output_dir: Annotated[
        str | None,
        typer.Option("--echo-output-dir", help="Override echo run artifact root"),
    ] = None,
    max_rounds: Annotated[int | None, typer.Option("--max-rounds", help="Forward to echo")]=None,
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable output")]=False,
) -> None:
    """Run the repo-local preview/live pipeline and persist one module-first bundle."""
    if not files:
        raise typer.BadParameter("--files is required")
    if mode not in {"preview", "live"}:
        raise typer.BadParameter("--mode must be preview or live")
    if mode == "live" and not allow_live_publish and loom_workflow:
        raise typer.BadParameter(
            "--allow-live-publish is required when using --mode live with --loom-workflow"
        )

    resolved_brand_id = _canonical_brand_id(brand, brand_id)
    resolved_pipeline_id = (
        _safe_slug(pipeline_id) if pipeline_id else f"pipeline_{uuid4().hex[:12]}"
    )
    if not resolved_pipeline_id:
        raise typer.BadParameter("--pipeline-id must contain letters or numbers")
    manifest_path = _pipeline_manifest_path(output_dir, resolved_pipeline_id)
    pipeline_dir = manifest_path.parent
    vox_dir = _module_dir(pipeline_dir, "vox")
    compass_dir = _module_dir(pipeline_dir, "compass")
    loom_dir = _module_dir(pipeline_dir, "loom")
    pulse_dir = _module_dir(pipeline_dir, "pulse")
    manifest = _default_pipeline_manifest(
        resolved_pipeline_id,
        persona=persona,
        brand=brand,
        brand_id=resolved_brand_id,
        brief=brief,
        files=[str(path.resolve()) for path in files],
        smoke=smoke,
        mode=mode,
        persona_eval=persona_eval,
        loom_workflow=loom_workflow,
    )
    _save_pipeline_manifest(manifest_path, manifest)

    try:
        if persona_eval:
            persona_eval_payload = _capture_member_json(
                "agentcy persona",
                [
                    "--json",
                    "test",
                    persona,
                    "--difficulty",
                    "stress",
                    "--save-report",
                ],
            )
            persona_eval_path = vox_dir / "persona_eval.json"
            _write_json(persona_eval_path, persona_eval_payload)
            manifest = _record_pipeline_step(
                manifest,
                "persona_eval",
                status="ok",
                data={"score": persona_eval_payload.get("score")},
            )
            manifest = _record_pipeline_artifact(
                manifest,
                "persona_eval",
                str(persona_eval_path),
            )
            _save_pipeline_manifest(manifest_path, manifest)

        voice_pack_path = vox_dir / "voice_pack.v1.json"
        voice_pack_payload = _capture_member_json(
            "agentcy persona",
            ["--json", "export", persona, "--to", "voice-pack.v1"],
        )
        if voice_pack_payload.get("brand_id") != resolved_brand_id:
            manifest = _record_degradation(
                manifest,
                "Vox exported a non-canonical brand_id for this pipeline bundle; "
                "the bundle copy was rewritten to match the pipeline brand lineage.",
            )
            voice_pack_payload = dict(voice_pack_payload)
            voice_pack_payload["brand_id"] = resolved_brand_id
        _write_json(voice_pack_path, voice_pack_payload)
        manifest = _record_pipeline_step(manifest, "voice_pack", status="ok")
        manifest = _record_pipeline_artifact(manifest, "voice_pack", str(voice_pack_path))
        _save_pipeline_manifest(manifest_path, manifest)

        brief_path = compass_dir / "brief.v1.json"
        compass_output_path = compass_dir / "plan.json"
        compass_command = [
            _resolve_bin("agentcy brand"),
            "plan",
            "run",
            brief,
            "--brand",
            brand,
            "--brand-id",
            resolved_brand_id,
            "--voice-pack-input",
            str(voice_pack_path),
            "--brief-v1-output",
            str(brief_path),
            "--output",
            str(compass_output_path),
            "-f",
            "json",
        ]
        compass_provider_used, compass_degraded = _run_compass_plan(
            compass_command,
            provider=compass_provider,
            cwd=Path(__file__).resolve().parents[2] / "compass",
        )
        if compass_degraded:
            manifest = _record_degradation(
                manifest,
                "Compass fell back to "
                f"BRANDOPS_LLM_PROVIDER={compass_provider_used} after the preferred "
                "provider failed schema validation or command execution.",
            )
        compass_payload = _load_json(compass_output_path)
        manifest = _record_pipeline_step(manifest, "brief", status="ok")
        manifest = _record_pipeline_artifact(manifest, "brief", str(brief_path))
        manifest = _record_pipeline_artifact(manifest, "compass_result", str(compass_output_path))
        manifest = _record_pipeline_step(
            manifest,
            "compass",
            status="degraded" if compass_degraded else "ok",
            data={
                "campaign": compass_payload.get("activation", {}),
                "provider": compass_provider_used,
            },
        )
        _save_pipeline_manifest(manifest_path, manifest)

        resolved_echo_output_dir = echo_output_dir or str(_module_dir(pipeline_dir, "echo"))
        echo_args = [
            "run",
            "--files",
            *(str(path.resolve()) for path in files),
            "--brief",
            str(brief_path),
            "--json",
            "--output-dir",
            resolved_echo_output_dir,
        ]
        if smoke:
            echo_args.append("--smoke")
        if max_rounds is not None:
            echo_args.extend(["--max-rounds", str(max_rounds)])

        echo_payload = _capture_member_json("agentcy forecast", echo_args)
        echo_run_id = str(echo_payload.get("run_id"))
        export_payload = _echo_artifacts_for_run(echo_run_id, resolved_echo_output_dir)
        artifacts = dict(export_payload.get("artifacts") or {})
        echo_run_dir = str(Path(resolved_echo_output_dir).resolve() / echo_run_id)
        manifest = _record_pipeline_step(
            manifest,
            "forecast",
            status="ok",
            data={"run_id": echo_run_id},
        )
        manifest = _record_pipeline_step(
            manifest,
            "echo",
            status="ok",
            data={"run_id": echo_run_id, "output_dir": echo_run_dir},
        )
        manifest = _record_pipeline_artifact(manifest, "echo_run_id", echo_run_id)
        manifest = _record_pipeline_artifact(manifest, "echo_run_dir", echo_run_dir)
        manifest = _record_pipeline_artifact(manifest, "forecast", artifacts.get("forecast_v1"))
        manifest = _record_pipeline_artifact(manifest, "echo_run_eval", artifacts.get("run_eval"))
        if not artifacts.get("forecast_v1"):
            manifest = _record_degradation(
                manifest,
                "Echo completed without a canonical forecast_v1 export; inspect "
                "the echo run directory directly.",
            )
        if not artifacts.get("run_eval"):
            manifest = _record_degradation(
                manifest,
                "Echo completed without a repo-local run_eval export; inspect "
                "the echo run directory directly.",
            )
        _save_pipeline_manifest(manifest_path, manifest)

        if loom_workflow:
            loom_run = _loom_envelope_data(
                _capture_loom_json(
                    [
                        "run",
                        loom_workflow,
                        "--brand",
                        brand,
                        "--brief-file",
                        str(brief_path),
                        "--json",
                    ]
                )
            )
            loom_run_path = loom_dir / "run.json"
            _write_json(loom_run_path, loom_run)
            loom_run_id = str(loom_run.get("id") or loom_run.get("run_id") or "")
            manifest = _record_pipeline_artifact(manifest, "loom_run", str(loom_run_path))
            manifest = _record_pipeline_artifact(manifest, "loom_run_id", loom_run_id)

            loom_step_data = {
                "run_id": loom_run_id,
                "workflow": loom_run.get("workflow"),
                "status": loom_run.get("status"),
                "current_step": loom_run.get("currentStep"),
            }

            if mode == "preview":
                manifest, publish_payload, run_result = _loom_review_publish(
                    manifest, loom_run_id, loom_dir, dry_run=True
                )
                inspect_payload = _capture_loom_json(["inspect", "run", loom_run_id, "--json"])
                inspect_path = loom_dir / "inspect.json"
                _write_json(inspect_path, inspect_payload)
                manifest = _record_pipeline_artifact(manifest, "loom_inspect", str(inspect_path))
                loom_step_data.update(
                    {
                        "status": (publish_payload.get("run") or {}).get("status"),
                        "run_result_status": run_result.get("status"),
                    }
                )
                preview_path = pulse_dir / "preview.json"
                _write_json(
                    preview_path,
                    {
                        "status": "skipped",
                        "mode": "preview",
                        "reason": (
                            "Preview mode stops before canonical performance.v1 unless "
                            "you later attach one with pipeline update."
                        ),
                    },
                )
                manifest = _record_pipeline_step(
                    manifest,
                    "pulse",
                    status="skipped",
                    data={"reason": "preview mode stops before canonical performance.v1"},
                )
                manifest = _record_pipeline_artifact(
                    manifest,
                    "pulse_preview",
                    str(preview_path),
                )
            else:
                manifest, _publish_payload, _run_result = _loom_review_publish(
                    manifest, loom_run_id, loom_dir, dry_run=False
                )
                manifest = _record_degradation(
                    manifest,
                    "Live mode completed the loom publish step, but Pulse still "
                    "needs a later pipeline update once canonical performance.v1 exists.",
                )
                manifest = _record_pipeline_step(
                    manifest,
                    "pulse",
                    status="skipped",
                    data={"reason": "waiting for canonical performance.v1"},
                )

            manifest = _record_pipeline_step(
                manifest,
                "loom",
                status="ok",
                data=loom_step_data,
            )
        else:
            manifest = _record_pipeline_step(
                manifest,
                "loom",
                status="skipped",
                data={"reason": "no --loom-workflow was requested"},
            )
            preview_path = pulse_dir / "preview.json"
            _write_json(
                preview_path,
                {
                    "status": "skipped",
                    "mode": mode,
                    "reason": (
                        "Pulse requires loom output and, for canonical performance, "
                        "published measurement input."
                    ),
                },
            )
            manifest = _record_pipeline_step(
                manifest,
                "pulse",
                status="skipped",
                data={"reason": "no loom workflow was requested"},
            )
            manifest = _record_pipeline_artifact(manifest, "pulse_preview", str(preview_path))

        manifest = _record_pipeline_artifact(manifest, "manifest", str(manifest_path))
        manifest = _finalize_pipeline_bundle(manifest_path, manifest)
    except Exception as exc:
        manifest = _record_pipeline_step(
            manifest,
            "pipeline",
            status="error",
            data={"error": str(exc)},
        )
        _save_pipeline_manifest(manifest_path, manifest)
        err.print(f"[red]error:[/red] {exc}")
        raise typer.Exit(1)

    data = {
        "manifest": str(manifest_path),
        "bundle": str(manifest.get("artifacts", {}).get("bundle_manifest", "")),
        "report": str(manifest.get("artifacts", {}).get("operator_report", "")),
        "pipeline": manifest,
    }
    if json_out:
        print(json.dumps({"status": "ok", "command": "pipeline.run", "data": data}, indent=2))
    else:
        console.print(f"[green]pipeline saved:[/green] {manifest_path}")


@pipeline_app.command("update")
def pipeline_update(
    manifest: Annotated[Path, typer.Option("--manifest", help="Pipeline manifest path")],
    run_result: Annotated[
        Path | None,
        typer.Option("--run-result", help="Canonical run_result.v1 path to attach"),
    ] = None,
    performance: Annotated[
        Path | None,
        typer.Option("--performance", help="Canonical performance.v1 path to attach"),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable output")]=False,
) -> None:
    """Backfill later-stage canonical artifact paths onto a saved pipeline manifest."""
    if run_result is None and performance is None:
        raise typer.BadParameter("Provide at least one of --run-result or --performance")

    pipeline_manifest = _load_json(manifest)
    pipeline_dir = manifest.parent

    if run_result is not None:
        run_result_path = run_result.resolve()
        run_result_payload = _load_json(run_result_path)
        if run_result_payload.get("artifact_type") != "run_result.v1":
            raise typer.BadParameter("--run-result must point to a run_result.v1 JSON file")
        localized_run_result = _copy_json_file(
            run_result_path,
            _module_dir(pipeline_dir, "loom") / "run_result.v1.json",
        )
        pipeline_manifest = _record_pipeline_artifact(
            pipeline_manifest,
            "run_result",
            str(localized_run_result),
        )
        pipeline_manifest = _record_pipeline_artifact(
            pipeline_manifest,
            "loom_run_id",
            str(run_result_payload.get("run_id") or ""),
        )
        pipeline_manifest = _record_pipeline_step(
            pipeline_manifest,
            "run_result",
            status="ok",
            data={
                "run_id": run_result_payload.get("run_id"),
                "workflow": run_result_payload.get("workflow"),
                "status": run_result_payload.get("status"),
            },
        )

    if performance is not None:
        performance_path = performance.resolve()
        performance_payload = _load_json(performance_path)
        if performance_payload.get("artifact_type") != "performance.v1":
            raise typer.BadParameter(
                "--performance must point to a performance.v1 JSON file"
            )
        localized_performance = _copy_json_file(
            performance_path,
            _module_dir(pipeline_dir, "pulse") / "performance.v1.json",
        )
        pipeline_manifest = _record_pipeline_artifact(
            pipeline_manifest,
            "performance",
            str(localized_performance),
        )
        pipeline_manifest = _record_pipeline_step(
            pipeline_manifest,
            "performance",
            status="ok",
            data={
                "performance_id": performance_payload.get("performance_id"),
                "run_id": performance_payload.get("run_id"),
                "measured_at": performance_payload.get("measured_at"),
            },
        )

    pipeline_manifest = _finalize_pipeline_bundle(manifest, pipeline_manifest)
    data = {
        "manifest": str(manifest),
        "bundle": str(pipeline_manifest.get("artifacts", {}).get("bundle_manifest", "")),
        "pipeline": pipeline_manifest,
    }
    if json_out:
        print(json.dumps({"status": "ok", "command": "pipeline.update", "data": data}, indent=2))
    else:
        console.print(f"[green]pipeline updated:[/green] {manifest}")


@pipeline_app.command("study")
def pipeline_study(
    manifest: Annotated[Path, typer.Option("--manifest", help="Pipeline manifest path")],
    performance: Annotated[
        Path | None,
        typer.Option("--performance", help="Override performance.v1 path"),
    ] = None,
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable output")]=False,
) -> None:
    """Run pulse study using paths auto-discovered from a pipeline manifest."""
    pipeline_manifest = _load_json(manifest)
    artifacts = dict(pipeline_manifest.get("artifacts") or {})
    performance_path = performance or (
        Path(artifacts["performance"]) if artifacts.get("performance") else None
    )
    if performance_path is None:
        raise typer.BadParameter(
            "--performance is required unless the pipeline manifest already records one"
        )

    pulse_args = [
        "study",
        "--pipeline-manifest",
        str(manifest),
        "--performance",
        str(performance_path),
        "--json",
    ]
    pulse_payload = _capture_member_json("agentcy metrics", pulse_args)
    study_payload = _pulse_envelope_data(pulse_payload)

    study_path = _module_dir(manifest.parent, "pulse") / "study.json"
    _write_json(study_path, study_payload)
    pipeline_manifest = _record_pipeline_artifact(
        pipeline_manifest,
        "performance",
        str(performance_path),
    )
    pipeline_manifest = _record_pipeline_artifact(
        pipeline_manifest,
        "study",
        str(study_path),
    )
    pipeline_manifest = _record_pipeline_step(
        pipeline_manifest,
        "study",
        status="ok",
        data={"study_verdict": study_payload.get("study_verdict")},
    )
    pipeline_manifest = _record_pipeline_step(
        pipeline_manifest,
        "pulse",
        status="ok",
        data={"study_verdict": study_payload.get("study_verdict")},
    )
    pipeline_manifest = _finalize_pipeline_bundle(manifest, pipeline_manifest)

    data = {
        "manifest": str(manifest),
        "study": str(study_path),
        "report": study_payload,
    }
    if json_out:
        print(json.dumps({"status": "ok", "command": "pipeline.study", "data": data}, indent=2))
    else:
        console.print(f"[green]study saved:[/green] {study_path}")


# ---------------------------------------------------------------------------
# catalog / quickstart / doctor
# ---------------------------------------------------------------------------


@app.command("catalog")
def catalog(
    json_out: Annotated[bool, typer.Option("--json", help="Machine-readable output")] = False,
) -> None:
    """Describe the suite, member ownership, and install profiles."""
    payload = _suite_catalog_payload()
    if json_out:
        print(json.dumps({"status": "ok", "command": "catalog", "data": payload}, indent=2))
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
            help="Install profile: python-suite | echo-simulation | loom-runtime | full-operator",
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
        print(json.dumps({"status": "ok", "command": "quickstart", "data": payload}, indent=2))
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
        ("vox", "agentcy persona", "python", ["agentcy persona", "--version"]),
        ("compass", "agentcy brand", "python", ["agentcy brand", "--help"]),
        ("echo", "agentcy forecast", "python", ["agentcy forecast", "doctor", "--json"]),
        ("loom", "agentcy studio", "node", None),
        ("pulse", "agentcy metrics", "python", ["agentcy metrics", "doctor", "--json"]),
    ]

    results: dict[str, dict[str, Any]] = {}
    all_ok = True

    for name, bin_name, runtime, probe_command in members:
        details = None
        if runtime == "node":
            resolved = _loom_bin()
            found = resolved is not None and node is not None
            reachable = found and _probe_member(_loom_command(["help", "--json"]))
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
        print(
            json.dumps(
                {
                    "status": "ok" if all_ok else "error",
                    "command": "doctor",
                    "data": results,
                }
            )
        )
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
