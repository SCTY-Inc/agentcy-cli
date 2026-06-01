"""agentcy pipeline — first-class orchestration over the member CLIs."""

from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Annotated, Any
from uuid import uuid4

import typer
from agentcy_protocols.output import envelope as _envelope
from agentcy_protocols.utils import load_json as _load_json
from agentcy_protocols.utils import write_json as _write_json

from agentcy import cli as _cli
from agentcy.cli import _OVERRIDES, _utc_now, console, err, pipeline_app


def _subprocess_env() -> dict[str, str]:
    return _cli._subprocess_env()


def _capture_member_json(bin_name: str, args: list[str]) -> dict[str, Any]:
    return _cli._capture_member_json(bin_name, args)


def _capture_studio_json(args: list[str]) -> dict[str, Any]:
    return _cli._capture_studio_json(args)


def _capture_optional_json(command: list[str]) -> dict[str, Any] | None:
    return _cli._capture_optional_json(command)


def _normalize_member_payload(payload: Any) -> dict[str, Any]:
    return _cli._normalize_member_payload(payload)


def _resolve_bin(bin_name: str) -> str:
    return _cli._resolve_bin(bin_name)


def _pipeline_root(output_dir: Path | None) -> Path:
    return (output_dir or Path("artifacts") / "pipelines").resolve()


def _pipeline_manifest_path(output_dir: Path | None, pipeline_id: str) -> Path:
    return _pipeline_root(output_dir) / pipeline_id / "manifest.json"


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


def _default_voice_pack_id(brand_id: str) -> str:
    return f"{brand_id}.voice.default"


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



# ---
def _select_studio_variant(studio_inspect: dict[str, Any] | None) -> dict[str, Any] | None:
    if not studio_inspect:
        return None
    data = dict(studio_inspect.get("data") or {})
    for artifact in data.get("artifacts") or []:
        if artifact.get("type") != "draft_set":
            continue
        variants = ((artifact.get("data") or {}).get("variants") or [])
        if variants:
            return variants[0]
    return None


def _write_operator_report(pipeline_dir: Path, manifest: dict[str, Any]) -> Path:
    artifacts = dict(manifest.get("artifacts") or {})
    forecast_eval = _read_json_if_exists(artifacts.get("forecast_run_eval"))
    forecast = _read_json_if_exists(artifacts.get("forecast"))
    measure_study = _read_json_if_exists(artifacts.get("study"))
    studio_inspect = _read_json_if_exists(artifacts.get("studio_inspect"))
    best_variant = _select_studio_variant(studio_inspect)

    lines = [
        f"# Pipeline report — {manifest.get('pipeline_id', 'unknown')}",
        "",
        "## Status",
        "",
        f"- Mode: {manifest.get('mode', 'preview')}",
        f"- Brand: {manifest.get('brand')}",
        f"- Brand ID: {manifest.get('brand_id')}",
    ]
    if manifest.get("persona"):
        lines.append(f"- Persona: {manifest.get('persona')}")

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

    if forecast_eval:
        summary = dict(forecast_eval.get("summary") or {})
        metrics = dict(forecast_eval.get("metrics") or {})
        lines.extend([
            "",
            "## Forecast run eval",
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

    if measure_study:
        lines.extend([
            "",
            "## Measure study",
            "",
            f"- Verdict: {measure_study.get('study_verdict', 'n/a')}",
            f"- Recommendation: {measure_study.get('recommendation', 'n/a')}",
        ])
    elif artifacts.get("measure_preview"):
        preview = _read_json_if_exists(artifacts.get("measure_preview")) or {}
        lines.extend([
            "",
            "## Measure",
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
    persona: str | None,
    brand: str,
    brand_id: str,
    brief: str,
    files: list[str],
    smoke: bool,
    mode: str,
    persona_eval: bool,
    with_forecast: bool,
    studio_workflow: str | None,
    studio_style: str | None,
    publish: bool,
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
        "with_forecast": with_forecast,
        "studio_workflow": studio_workflow,
        "studio_style": studio_style,
        "publish": publish,
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


def _studio_review_publish(
    manifest: dict[str, Any],
    studio_run_id: str,
    studio_dir: Path,
    *,
    dry_run: bool,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Review + publish a Studio run. Returns (manifest, publish_payload, run_result)."""
    review_payload = _studio_envelope_data(
        _capture_studio_json(["review", "approve", studio_run_id, "--json"])
    )
    review_path = studio_dir / "review.json"
    _write_json(review_path, review_payload)
    manifest = _record_pipeline_artifact(manifest, "studio_review", str(review_path))

    publish_cmd = ["publish", studio_run_id, "--dry-run", "--json"] if dry_run else [
        "publish", studio_run_id, "--json"
    ]
    publish_payload = _studio_envelope_data(_capture_studio_json(publish_cmd))
    publish_path = studio_dir / "publish.json"
    _write_json(publish_path, publish_payload)
    manifest = _record_pipeline_artifact(manifest, "studio_publish", str(publish_path))

    run_result = dict(publish_payload.get("runResult") or {})
    if run_result:
        run_result_path = studio_dir / "run_result.v1.json"
        _write_json(run_result_path, run_result)
        manifest = _record_pipeline_artifact(manifest, "run_result", str(run_result_path))

    return manifest, publish_payload, run_result


def _forecast_artifacts_for_run(run_id: str, output_dir: str | None) -> dict[str, Any]:
    args = ["runs", "export", run_id, "--json"]
    if output_dir:
        args.extend(["--output-dir", output_dir])
    return _capture_member_json("agentcy-forecast", args)


def _measure_envelope_data(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("data") or payload)


def _studio_envelope_data(payload: dict[str, Any]) -> dict[str, Any]:
    return dict(payload.get("data") or payload)


def _run_briefs_plan(
    command: list[str],
    *,
    provider: str | None = None,
    cwd: Path | None = None,
) -> tuple[str, bool]:
    supported = {"mock", "gemini", "anthropic", "claude-cli"}
    preferred = (
        provider
        or os.environ.get("AGENTCY_BRIEFS_LLM_PROVIDER")
        or _OVERRIDES.provider
        or os.environ.get("LLM_PROVIDER")
        or "mock"
    ).strip()
    if preferred not in supported:
        preferred = "mock"

    tried: list[str] = []
    for candidate in [preferred, *(["mock"] if preferred != "mock" else [])]:
        tried.append(candidate)
        env = _subprocess_env()
        env["AGENTCY_BRIEFS_LLM_PROVIDER"] = candidate
        model = os.environ.get("AGENTCY_BRIEFS_LLM_MODEL") or _OVERRIDES.model or os.environ.get(
            "CLAUDE_MODEL"
        )
        if model:
            env.setdefault("AGENTCY_BRIEFS_LLM_MODEL", model)
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
    raise RuntimeError(f"Briefs failed for providers: {', '.join(tried)}")

# ---
@pipeline_app.command("run")
def pipeline_run(
    brand: Annotated[str, typer.Option("--brand", help="Brand name for briefs/studio")],
    brief: Annotated[str, typer.Option("--brief", help="Campaign brief text")],
    persona: Annotated[
        str | None,
        typer.Option("--persona", help="Optional persona name to export via agentcy-voice"),
    ] = None,
    files: Annotated[
        list[Path] | None,
        typer.Option("--files", help="Source files for optional forecast"),
    ] = None,
    smoke: Annotated[bool, typer.Option("--smoke", help="Use forecast smoke mode")]=False,
    mode: Annotated[
        str,
        typer.Option("--mode", help="Pipeline mode: preview or live"),
    ] = "preview",
    brand_id: Annotated[
        str | None,
        typer.Option("--brand-id", help="Canonical brand lineage ID override"),
    ] = None,
    briefs_provider: Annotated[
        str | None,
        typer.Option("--briefs-provider", help="Preferred Briefs LLM provider"),
    ] = None,
    persona_eval: Annotated[
        bool,
        typer.Option("--persona-eval", help="Run and save a stress eval before export"),
    ] = False,
    with_forecast: Annotated[
        bool,
        typer.Option("--with-forecast", help="Run Forecast with the generated brief and --files"),
    ] = False,
    studio_workflow: Annotated[
        str | None,
        typer.Option(
            "--studio-workflow",
            help="Studio workflow to run after the brief; use 'none' to skip",
        ),
    ] = "social.post",
    style: Annotated[
        str | None,
        typer.Option("--style", help="Studio DESIGN.md visual style profile to render"),
    ] = None,
    publish: Annotated[
        bool,
        typer.Option(
            "--publish",
            help="Approve and publish the Studio run; preview mode uses a dry run",
        ),
    ] = False,
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
    forecast_output_dir: Annotated[
        str | None,
        typer.Option("--forecast-output-dir", help="Override forecast run artifact root"),
    ] = None,
    max_rounds: Annotated[
        int | None,
        typer.Option("--max-rounds", help="Forward to forecast"),
    ] = None,
    json_out: Annotated[
        bool,
        typer.Option("--json", help="Machine-readable output"),
    ] = False,
) -> None:
    """Run the repo-local essential brand-to-artifact pipeline."""
    resolved_files = list(files or [])
    if mode not in {"preview", "live"}:
        raise typer.BadParameter("--mode must be preview or live")
    if persona_eval and not persona:
        raise typer.BadParameter("--persona is required when using --persona-eval")
    if with_forecast and not resolved_files:
        raise typer.BadParameter("--files is required when using --with-forecast")
    if mode == "live" and publish and not allow_live_publish:
        raise typer.BadParameter(
            "--allow-live-publish is required when using --mode live with --publish"
        )
    if studio_workflow and studio_workflow.strip().lower() in {"none", "skip", "false"}:
        studio_workflow = None

    resolved_brand_id = _canonical_brand_id(brand, brand_id)
    resolved_pipeline_id = (
        _safe_slug(pipeline_id) if pipeline_id else f"pipeline_{uuid4().hex[:12]}"
    )
    if not resolved_pipeline_id:
        raise typer.BadParameter("--pipeline-id must contain letters or numbers")
    manifest_path = _pipeline_manifest_path(output_dir, resolved_pipeline_id)
    pipeline_dir = manifest_path.parent
    voice_dir = _module_dir(pipeline_dir, "voice")
    briefs_dir = _module_dir(pipeline_dir, "briefs")
    studio_dir = _module_dir(pipeline_dir, "studio")
    measure_dir = _module_dir(pipeline_dir, "measure")
    manifest = _default_pipeline_manifest(
        resolved_pipeline_id,
        persona=persona,
        brand=brand,
        brand_id=resolved_brand_id,
        brief=brief,
        files=[str(path.resolve()) for path in resolved_files],
        smoke=smoke,
        mode=mode,
        persona_eval=persona_eval,
        with_forecast=with_forecast,
        studio_workflow=studio_workflow,
        studio_style=style,
        publish=publish,
    )
    _save_pipeline_manifest(manifest_path, manifest)

    try:
        voice_pack_path: Path | None = None
        voice_pack_id = _default_voice_pack_id(resolved_brand_id)
        if persona_eval:
            persona_eval_payload = _capture_member_json(
                "agentcy-voice",
                [
                    "--json",
                    "test",
                    persona,
                    "--difficulty",
                    "stress",
                    "--save-report",
                ],
            )
            persona_eval_path = voice_dir / "persona_eval.json"
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

        if persona:
            voice_pack_path = voice_dir / "voice_pack.v1.json"
            voice_pack_payload = _capture_member_json(
                "agentcy-voice",
                ["--json", "export", persona, "--to", "voice-pack.v1"],
            )
            voice_pack_id = str(voice_pack_payload.get("voice_pack_id") or voice_pack_id)
            if voice_pack_payload.get("brand_id") != resolved_brand_id:
                manifest = _record_degradation(
                    manifest,
                    "Voice exported a non-canonical brand_id for this pipeline bundle; "
                    "the bundle copy was rewritten to match the pipeline brand lineage.",
                )
                voice_pack_payload = dict(voice_pack_payload)
                voice_pack_payload["brand_id"] = resolved_brand_id
            _write_json(voice_pack_path, voice_pack_payload)
            manifest = _record_pipeline_step(
                manifest,
                "voice_pack",
                status="ok",
                data={"voice_pack_id": voice_pack_id},
            )
            manifest = _record_pipeline_artifact(manifest, "voice_pack", str(voice_pack_path))
        else:
            manifest = _record_pipeline_step(
                manifest,
                "voice_pack",
                status="skipped",
                data={
                    "reason": "default pipeline uses the brand foundation directly",
                    "voice_pack_id": voice_pack_id,
                },
            )
        _save_pipeline_manifest(manifest_path, manifest)

        brief_path = briefs_dir / "brief.v1.json"
        briefs_output_path = briefs_dir / "plan.json"
        voice_args = (
            ["--voice-pack-input", str(voice_pack_path)]
            if voice_pack_path is not None
            else ["--voice-pack-id", voice_pack_id]
        )
        briefs_command = [
            _resolve_bin("agentcy-briefs"),
            "plan",
            "run",
            brief,
            "--brand",
            brand,
            "--brand-id",
            resolved_brand_id,
            *voice_args,
            "--brief-v1-output",
            str(brief_path),
            "--output",
            str(briefs_output_path),
            "-f",
            "json",
        ]
        briefs_provider_used, briefs_degraded = _run_briefs_plan(
            briefs_command,
            provider=briefs_provider,
            cwd=Path(__file__).resolve().parents[1],
        )
        if briefs_degraded:
            manifest = _record_degradation(
                manifest,
                "Briefs fell back to "
                f"AGENTCY_BRIEFS_LLM_PROVIDER={briefs_provider_used} after the preferred "
                "provider failed schema validation or command execution.",
            )
        briefs_payload = _load_json(briefs_output_path)
        manifest = _record_pipeline_step(manifest, "brief", status="ok")
        manifest = _record_pipeline_artifact(manifest, "brief", str(brief_path))
        manifest = _record_pipeline_artifact(manifest, "briefs_result", str(briefs_output_path))
        manifest = _record_pipeline_step(
            manifest,
            "briefs",
            status="degraded" if briefs_degraded else "ok",
            data={
                "campaign": briefs_payload.get("activation", {}),
                "provider": briefs_provider_used,
            },
        )
        _save_pipeline_manifest(manifest_path, manifest)

        if with_forecast:
            resolved_forecast_output_dir = forecast_output_dir or str(
                _module_dir(pipeline_dir, "forecast")
            )
            forecast_args = [
                "run",
                "--files",
                *(str(path.resolve()) for path in resolved_files),
                "--brief",
                str(brief_path),
                "--json",
                "--output-dir",
                resolved_forecast_output_dir,
            ]
            if smoke:
                forecast_args.append("--smoke")
            if max_rounds is not None:
                forecast_args.extend(["--max-rounds", str(max_rounds)])

            forecast_payload = _capture_member_json("agentcy-forecast", forecast_args)
            forecast_run_id = str(forecast_payload.get("run_id"))
            export_payload = _forecast_artifacts_for_run(
                forecast_run_id,
                resolved_forecast_output_dir,
            )
            artifacts = dict(export_payload.get("artifacts") or {})
            forecast_run_dir = str(Path(resolved_forecast_output_dir).resolve() / forecast_run_id)
            manifest = _record_pipeline_step(
                manifest,
                "forecast",
                status="ok",
                data={"run_id": forecast_run_id, "output_dir": forecast_run_dir},
            )
            manifest = _record_pipeline_artifact(manifest, "forecast_run_id", forecast_run_id)
            manifest = _record_pipeline_artifact(manifest, "forecast_run_dir", forecast_run_dir)
            manifest = _record_pipeline_artifact(manifest, "forecast", artifacts.get("forecast_v1"))
            manifest = _record_pipeline_artifact(
                manifest,
                "forecast_run_eval",
                artifacts.get("run_eval"),
            )
            if not artifacts.get("forecast_v1"):
                manifest = _record_degradation(
                    manifest,
                    "Forecast completed without a canonical forecast_v1 export; inspect "
                    "the forecast run directory directly.",
                )
            if not artifacts.get("run_eval"):
                manifest = _record_degradation(
                    manifest,
                    "Forecast completed without a repo-local run_eval export; inspect "
                    "the forecast run directory directly.",
                )
        else:
            manifest = _record_pipeline_step(
                manifest,
                "forecast",
                status="skipped",
                data={"reason": "use --with-forecast with --files to run Forecast"},
            )
        _save_pipeline_manifest(manifest_path, manifest)

        if studio_workflow:
            studio_cmd = [
                "run",
                studio_workflow,
                "--brand",
                brand,
                "--brief-file",
                str(brief_path),
            ]
            if style:
                studio_cmd.extend(["--style", style])
            studio_cmd.append("--json")
            studio_run = _studio_envelope_data(
                _capture_studio_json(studio_cmd)
            )
            studio_run_path = studio_dir / "run.json"
            _write_json(studio_run_path, studio_run)
            studio_run_id = str(studio_run.get("id") or studio_run.get("run_id") or "")
            manifest = _record_pipeline_artifact(manifest, "studio_run", str(studio_run_path))
            manifest = _record_pipeline_artifact(manifest, "studio_run_id", studio_run_id)

            studio_step_data = {
                "run_id": studio_run_id,
                "workflow": studio_run.get("workflow"),
                "status": studio_run.get("status"),
                "current_step": studio_run.get("currentStep"),
            }

            inspect_payload = _capture_studio_json(["inspect", "run", studio_run_id, "--json"])
            inspect_path = studio_dir / "inspect.json"
            _write_json(inspect_path, inspect_payload)
            manifest = _record_pipeline_artifact(manifest, "studio_inspect", str(inspect_path))

            if publish:
                manifest, publish_payload, run_result = _studio_review_publish(
                    manifest,
                    studio_run_id,
                    studio_dir,
                    dry_run=(mode == "preview"),
                )
                studio_step_data.update(
                    {
                        "status": (publish_payload.get("run") or {}).get("status"),
                        "run_result_status": run_result.get("status"),
                    }
                )
                preview_path = measure_dir / "preview.json"
                _write_json(
                    preview_path,
                    {
                        "status": "skipped",
                        "mode": mode,
                        "reason": (
                            "Publishing completed, but canonical performance.v1 is attached "
                            "later with pipeline update."
                        ),
                    },
                )
                manifest = _record_pipeline_step(
                    manifest,
                    "measure",
                    status="skipped",
                    data={
                        "reason": (
                            "canonical performance.v1 is attached later with pipeline update"
                        )
                    },
                )
                manifest = _record_pipeline_artifact(
                    manifest,
                    "measure_preview",
                    str(preview_path),
                )
            else:
                preview_path = measure_dir / "preview.json"
                _write_json(
                    preview_path,
                    {
                        "status": "skipped",
                        "mode": mode,
                        "reason": (
                            "Essential pipeline stops at review-ready Studio artifacts. "
                            "Use --publish to approve and publish."
                        ),
                    },
                )
                manifest = _record_pipeline_step(
                    manifest,
                    "measure",
                    status="skipped",
                    data={"reason": "no publish output in essential mode"},
                )
                manifest = _record_pipeline_artifact(manifest, "measure_preview", str(preview_path))

            manifest = _record_pipeline_step(
                manifest,
                "studio",
                status="ok",
                data=studio_step_data,
            )
        else:
            manifest = _record_pipeline_step(
                manifest,
                "studio",
                status="skipped",
                data={"reason": "no --studio-workflow was requested"},
            )
            preview_path = measure_dir / "preview.json"
            _write_json(
                preview_path,
                {
                    "status": "skipped",
                    "mode": mode,
                    "reason": (
                        "Measure requires studio output and, for canonical performance, "
                        "published measurement input."
                    ),
                },
            )
            manifest = _record_pipeline_step(
                manifest,
                "measure",
                status="skipped",
                data={"reason": "no studio workflow was requested"},
            )
            manifest = _record_pipeline_artifact(manifest, "measure_preview", str(preview_path))

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
        print(json.dumps(_envelope(data, command="pipeline.run"), indent=2))
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
            _module_dir(pipeline_dir, "studio") / "run_result.v1.json",
        )
        pipeline_manifest = _record_pipeline_artifact(
            pipeline_manifest,
            "run_result",
            str(localized_run_result),
        )
        pipeline_manifest = _record_pipeline_artifact(
            pipeline_manifest,
            "studio_run_id",
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
            _module_dir(pipeline_dir, "measure") / "performance.v1.json",
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
        print(json.dumps(_envelope(data, command="pipeline.update"), indent=2))
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
    """Run measure study using paths auto-discovered from a pipeline manifest."""
    pipeline_manifest = _load_json(manifest)
    artifacts = dict(pipeline_manifest.get("artifacts") or {})
    performance_path = performance or (
        Path(artifacts["performance"]) if artifacts.get("performance") else None
    )
    if performance_path is None:
        raise typer.BadParameter(
            "--performance is required unless the pipeline manifest already records one"
        )

    measure_args = [
        "study",
        "--pipeline-manifest",
        str(manifest),
        "--performance",
        str(performance_path),
        "--json",
    ]
    measure_payload = _capture_member_json("agentcy-measure", measure_args)
    study_payload = _measure_envelope_data(measure_payload)

    study_path = _module_dir(manifest.parent, "measure") / "study.json"
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
        "measure",
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
        print(json.dumps(_envelope(data, command="pipeline.study"), indent=2))
    else:
        console.print(f"[green]study saved:[/green] {study_path}")


# ---------------------------------------------------------------------------
# catalog / quickstart / doctor
# ---------------------------------------------------------------------------
