from __future__ import annotations

from pathlib import Path
from typing import Any

from agentcy.protocols.utils import load_json_optional

from .calibration import build_calibration_report

_load_json = load_json_optional


def _resolve_study_paths(
    forecast_path: Path | str | None,
    performance_path: Path | str | None,
    *,
    echo_eval_path: Path | str | None = None,
    persona_eval_path: Path | str | None = None,
    pipeline_manifest_path: Path | str | None = None,
    echo_run_dir: Path | str | None = None,
) -> dict[str, Any]:
    forecast = Path(forecast_path) if forecast_path is not None else None
    performance = Path(performance_path) if performance_path is not None else None
    echo_eval = Path(echo_eval_path) if echo_eval_path is not None else None
    persona_eval = Path(persona_eval_path) if persona_eval_path is not None else None

    if pipeline_manifest_path is not None:
        manifest = _load_json(pipeline_manifest_path) or {}
        artifacts = dict(manifest.get("artifacts") or {})
        if forecast is None and artifacts.get("forecast"):
            forecast = Path(artifacts["forecast"])
        if performance is None and artifacts.get("performance"):
            performance = Path(artifacts["performance"])
        if echo_eval is None and artifacts.get("echo_run_eval"):
            echo_eval = Path(artifacts["echo_run_eval"])
        if persona_eval is None and artifacts.get("persona_eval"):
            persona_eval = Path(artifacts["persona_eval"])
        if echo_run_dir is None and artifacts.get("echo_run_dir"):
            echo_run_dir = Path(artifacts["echo_run_dir"])

    if echo_run_dir is not None:
        run_dir = Path(echo_run_dir)
        if forecast is None:
            candidate = run_dir / "forecast" / "forecast.v1.json"
            if candidate.exists():
                forecast = candidate
        if echo_eval is None:
            candidate = run_dir / "eval" / "run_eval.v1.json"
            if candidate.exists():
                echo_eval = candidate

    if forecast is None:
        raise ValueError(
            "forecast path is required unless it can be resolved from pipeline metadata"
        )
    if performance is None:
        raise ValueError(
            "performance path is required unless it can be resolved from pipeline metadata"
        )

    return {
        "forecast_path": forecast,
        "performance_path": performance,
        "echo_eval_path": echo_eval,
        "persona_eval_path": persona_eval,
    }


def build_study_report(
    forecast_path: Path | str | None,
    performance_path: Path | str | None,
    *,
    echo_eval_path: Path | str | None = None,
    persona_eval_path: Path | str | None = None,
    pipeline_manifest_path: Path | str | None = None,
    echo_run_dir: Path | str | None = None,
) -> dict[str, Any]:
    paths = _resolve_study_paths(
        forecast_path,
        performance_path,
        echo_eval_path=echo_eval_path,
        persona_eval_path=persona_eval_path,
        pipeline_manifest_path=pipeline_manifest_path,
        echo_run_dir=echo_run_dir,
    )
    calibration = build_calibration_report(paths["forecast_path"], paths["performance_path"])
    echo_eval = _load_json(paths["echo_eval_path"])
    persona_eval = _load_json(paths["persona_eval_path"])

    report: dict[str, Any] = {
        "forecast_id": calibration["forecast_id"],
        "performance_id": calibration["performance_id"],
        "brief_id": calibration["brief_id"],
        "brand_id": calibration["brand_id"],
        "alignment": calibration["alignment"],
        "metric_leaders": calibration["metric_leaders"],
        "calibration_recommendation": calibration["recommendation"],
        "synthetic_signals": {},
        "risks": [],
    }

    if echo_eval is not None:
        metrics = dict(echo_eval.get("metrics") or {})
        summary = dict(echo_eval.get("summary") or {})
        report["synthetic_signals"]["echo_run_eval"] = {
            "activity_pattern": summary.get("activity_pattern"),
            "thesis": summary.get("thesis"),
            "round_coverage_ratio": metrics.get("round_coverage_ratio"),
            "peak_round_share": metrics.get("peak_round_share"),
            "top_agent_share": metrics.get("top_agent_share"),
            "coverage_score": metrics.get("coverage_score"),
            "local_diversity_score": metrics.get("local_diversity_score"),
            "complexity_score": metrics.get("complexity_score"),
            "critic_rejection_rate": metrics.get("critic_rejection_rate"),
        }
        round_coverage_ratio = metrics.get("round_coverage_ratio")
        if isinstance(round_coverage_ratio, (int, float)) and round_coverage_ratio < 0.5:
            report["risks"].append(
                "simulation coverage was shallow relative to the planned run horizon"
            )
        top_agent_share = metrics.get("top_agent_share")
        if isinstance(top_agent_share, (int, float)) and top_agent_share > 0.6:
            report["risks"].append("one agent dominated simulated activity")
        coverage_score = metrics.get("coverage_score")
        if isinstance(coverage_score, (int, float)) and coverage_score < 0.5:
            report["risks"].append(
                "synthetic coverage stayed narrow across the configured run space"
            )
        local_diversity_score = metrics.get("local_diversity_score")
        if isinstance(local_diversity_score, (int, float)) and local_diversity_score < 0.4:
            report["risks"].append("synthetic coverage stayed narrow within each covered scenario")
        complexity_score = metrics.get("complexity_score")
        if isinstance(complexity_score, (int, float)) and complexity_score < 0.35:
            report["risks"].append("synthetic complexity stayed too low to probe hard cases")
        critic_rejection_rate = metrics.get("critic_rejection_rate")
        if isinstance(critic_rejection_rate, (int, float)) and critic_rejection_rate > 0.2:
            report["risks"].append("critic rejected too many simulated actions")
        for risk in echo_eval.get("risks", []):
            if risk not in report["risks"]:
                report["risks"].append(risk)

    if persona_eval is not None:
        difficulty_scores = dict(persona_eval.get("difficulty_scores") or {})
        report["synthetic_signals"]["persona_eval"] = {
            "score": persona_eval.get("score"),
            "stress_score": difficulty_scores.get("stress"),
            "boundary_pass_rate": persona_eval.get("boundary_pass_rate"),
            "failure_modes": persona_eval.get("failure_modes", []),
        }
        stress_score = difficulty_scores.get("stress")
        if isinstance(stress_score, (int, float)) and stress_score < 0.7:
            report["risks"].append("persona behavior degraded under stress cases")
        boundary_pass_rate = persona_eval.get("boundary_pass_rate")
        if isinstance(boundary_pass_rate, (int, float)) and boundary_pass_rate < 0.8:
            report["risks"].append("persona boundary adherence was inconsistent")

    report["study_verdict"] = (
        "guarded" if report["risks"] else calibration["alignment"]["verdict"]
    )
    if report["risks"]:
        report["recommendation"] = (
            calibration["recommendation"]
            + " Review the synthetic-signal risks before promoting the next run unchanged."
        )
    else:
        report["recommendation"] = calibration["recommendation"]

    return report
