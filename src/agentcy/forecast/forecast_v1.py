"""Canonical completed forecast.v1 projection for agentcy-echo runs."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")


class ForecastWriter(BaseModel):
    repo: Literal["cli-mirofish"] = "cli-mirofish"
    module: Literal["agentcy-echo"] = "agentcy-echo"


class ForecastSummary(BaseModel):
    thesis: str = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    recommended_action: str | None = None


class ForecastScenario(BaseModel):
    scenario_id: str
    label: str = Field(min_length=1)
    probability: float = Field(ge=0, le=1)
    narrative: str = Field(min_length=1)
    drivers: list[str] = Field(default_factory=list)
    implications: list[str] = Field(default_factory=list)

    @field_validator("scenario_id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not ID_PATTERN.match(value):
            raise ValueError("scenario_id must match canonical pattern")
        return value


class ForecastLineage(BaseModel):
    source_brief_id: str
    source_voice_pack_id: str | None = None
    campaign_id: str | None = None
    signal_id: str | None = None

    @field_validator("source_brief_id", "source_voice_pack_id", "campaign_id", "signal_id")
    @classmethod
    def _validate_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not ID_PATTERN.match(value):
            raise ValueError("lineage IDs must match canonical pattern")
        return value


class ForecastProvenance(BaseModel):
    project_id: str | None = None
    graph_id: str | None = None
    simulation_id: str | None = None
    report_id: str | None = None

    @field_validator("project_id", "graph_id", "simulation_id", "report_id")
    @classmethod
    def _validate_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not ID_PATTERN.match(value):
            raise ValueError("provenance IDs must match canonical pattern")
        return value


class ForecastArtifacts(BaseModel):
    report_path: str | None = None
    snapshot_paths: list[str] = Field(default_factory=list)


class ForecastV1(BaseModel):
    artifact_type: Literal["forecast.v1"]
    schema_version: Literal["v1"]
    forecast_id: str
    brief_id: str
    brand_id: str
    writer: ForecastWriter
    status: Literal["completed"]
    completed_at: str
    timeframe: str | None = None
    summary: ForecastSummary
    scenarios: list[ForecastScenario] = Field(min_length=1)
    lineage: ForecastLineage
    provenance: ForecastProvenance | None = None
    artifacts: ForecastArtifacts | None = None

    @field_validator("forecast_id", "brief_id", "brand_id")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        if not ID_PATTERN.match(value):
            raise ValueError("forecast IDs must match canonical pattern")
        return value


def _load_json(path: Path) -> dict[str, Any] | list[Any] | None:
    # Returns list | dict | None — broader than agentcy_protocols.utils.load_json
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _first_non_empty(*values: Any) -> str:
    for value in values:
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_thesis(report_meta: dict[str, Any], report_markdown: str, requirement: str) -> str:
    outline = report_meta.get("outline") or {}
    thesis = _first_non_empty(
        outline.get("summary"),
        _extract_exec_summary(report_markdown),
        report_meta.get("simulation_requirement"),
        requirement,
    )
    return thesis or "Simulation completed with a forecast synthesized from the persisted MiroFish run artifacts."


def _extract_exec_summary(markdown: str) -> str:
    if not markdown:
        return ""
    match = re.search(r"\*\*Executive Summary:\*\*\s*(.+?)(?:\n\n|$)", markdown, re.DOTALL)
    if match:
        return re.sub(r"\s+", " ", match.group(1)).strip()
    for paragraph in markdown.split("\n\n"):
        cleaned = paragraph.strip().lstrip("#- ")
        if cleaned:
            return re.sub(r"\s+", " ", cleaned)
    return ""


def _confidence_from_timeline(timeline: list[dict[str, Any]]) -> float:
    if not timeline:
        return 0.5
    total_actions = sum(max(0, int(item.get("total_actions", 0))) for item in timeline)
    if total_actions <= 0:
        return 0.35
    active_rounds = sum(1 for item in timeline if int(item.get("total_actions", 0)) > 0)
    concentration = max(int(item.get("total_actions", 0)) for item in timeline) / total_actions
    round_factor = active_rounds / max(len(timeline), 1)
    confidence = 0.45 + (0.35 * concentration) + (0.20 * round_factor)
    return round(min(confidence, 0.95), 2)


def _timeframe(report_meta: dict[str, Any], requirement: str, timeline: list[dict[str, Any]]) -> str | None:
    text = _first_non_empty(report_meta.get("simulation_requirement"), requirement)
    match = re.search(r"over the next ([^.\n]+)", text, re.IGNORECASE)
    if match:
        return match.group(1).strip().replace(" ", "-")
    if timeline:
        return f"{len(timeline)}-round-simulation"
    return None


def _recommended_action(brief_payload: dict[str, Any] | None) -> str | None:
    if not brief_payload:
        return None
    strategy = brief_payload.get("strategy") or {}
    angle = (strategy.get("angle") or "").strip()
    cta = (strategy.get("cta") or "").strip()
    if angle and cta:
        return f"Lead with {angle.lower()} and use the brief CTA: {cta}"
    return cta or angle or None


def _scenario_driver_names(top_agents: list[dict[str, Any]], limit: int = 3) -> list[str]:
    names = []
    for agent in top_agents[:limit]:
        name = str(agent.get("agent_name") or "").strip()
        if name:
            names.append(f"High activity from {name}.")
    return names


def _build_scenarios(
    forecast_id: str,
    thesis: str,
    timeline: list[dict[str, Any]],
    top_agents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    total_actions = sum(int(item.get("total_actions", 0)) for item in timeline)
    active_rounds = sum(1 for item in timeline if int(item.get("total_actions", 0)) > 0)
    dominant_round = max(timeline, key=lambda item: int(item.get("total_actions", 0)), default={})
    concentrated = bool(timeline) and int(dominant_round.get("total_actions", 0)) == total_actions and total_actions > 0

    scenarios = [
        {
            "scenario_id": f"{forecast_id}.scenario.base",
            "label": "primary-forecast",
            "probability": 0.58,
            "narrative": thesis,
            "drivers": _scenario_driver_names(top_agents),
            "implications": [
                "Treat the report thesis as the default planning baseline.",
            ],
        }
    ]

    if concentrated:
        scenarios.append(
            {
                "scenario_id": f"{forecast_id}.scenario.spike",
                "label": "early-attention-spike",
                "probability": 0.27,
                "narrative": "Most observable discourse clustered into an early burst, suggesting quick attention formation with limited later evolution.",
                "drivers": [
                    f"Round {dominant_round.get('round_num', 0)} contained most of the simulated activity.",
                    *(_scenario_driver_names(top_agents, limit=2)),
                ],
                "implications": [
                    "Front-load the strongest framing.",
                    "Expect less benefit from a long tail of follow-up discussion.",
                ],
            }
        )

    if active_rounds <= 1:
        scenarios.append(
            {
                "scenario_id": f"{forecast_id}.scenario.low-followthrough",
                "label": "limited-follow-through",
                "probability": 0.15,
                "narrative": "The run completed, but sustained multi-round momentum remained limited, so follow-through risk should be treated as a secondary scenario.",
                "drivers": [
                    f"Only {active_rounds} round(s) showed non-zero activity.",
                ],
                "implications": [
                    "Pair launch messaging with a concrete follow-up prompt.",
                ],
            }
        )

    total_probability = sum(item["probability"] for item in scenarios)
    if total_probability > 0:
        scale = 1 / total_probability
        for item in scenarios:
            item["probability"] = round(item["probability"] * scale, 2)
        drift = round(1 - sum(item["probability"] for item in scenarios), 2)
        scenarios[0]["probability"] = round(scenarios[0]["probability"] + drift, 2)
    return scenarios


def build_completed_forecast_v1(manifest: dict[str, Any], run_dir: str | Path) -> ForecastV1:
    if manifest.get("status") != "completed":
        raise ValueError("forecast.v1 export is only available for completed runs")

    imported_lineage = dict(manifest.get("imported_lineage") or {})
    brief_id = imported_lineage.get("brief_id")
    brand_id = imported_lineage.get("brand_id")
    if not brief_id or not brand_id:
        raise ValueError("completed forecast export requires persisted canonical brief lineage")

    run_path = Path(run_dir)
    report_meta = _load_json(run_path / "report" / "meta.json") or {}
    report_summary = _load_json(run_path / "report" / "summary.json") or {}
    timeline = _load_json(run_path / "simulation" / "timeline.json") or []
    top_agents = _load_json(run_path / "simulation" / "top_agents.json") or []
    report_markdown = _load_text(run_path / "report" / "report.md")
    brief_payload = _load_json(run_path / "input" / "brief.v1.json")

    completed_at = _first_non_empty(
        report_meta.get("completed_at"),
        manifest.get("updated_at"),
        manifest.get("created_at"),
    )
    forecast_id = f"{brand_id}.forecast.{manifest['run_id']}"
    thesis = _extract_thesis(report_meta, report_markdown, manifest.get("requirement", ""))

    artifacts = dict(manifest.get("artifacts") or {})
    snapshot_paths = [
        rel_path
        for key, rel_path in artifacts.items()
        if key in {"swarm_overview", "cluster_map", "timeline", "platform_split"}
    ]

    payload = {
        "artifact_type": "forecast.v1",
        "schema_version": "v1",
        "forecast_id": forecast_id,
        "brief_id": brief_id,
        "brand_id": brand_id,
        "writer": {"repo": "cli-mirofish", "module": "agentcy-echo"},
        "status": "completed",
        "completed_at": completed_at,
        "summary": {
            "thesis": thesis,
            "confidence": _confidence_from_timeline(list(timeline)),
            "recommended_action": _recommended_action(brief_payload if isinstance(brief_payload, dict) else None),
        },
        "scenarios": _build_scenarios(forecast_id, thesis, list(timeline), list(top_agents)),
        "lineage": {
            "source_brief_id": brief_id,
            "source_voice_pack_id": imported_lineage.get("source_voice_pack_id"),
            "campaign_id": imported_lineage.get("campaign_id"),
            "signal_id": imported_lineage.get("signal_id"),
        },
        "provenance": {
            "project_id": manifest.get("project_id") or report_summary.get("project_id"),
            "graph_id": manifest.get("graph_id") or report_summary.get("graph_id") or report_meta.get("graph_id"),
            "simulation_id": manifest.get("simulation_id") or report_summary.get("simulation_id") or report_meta.get("simulation_id"),
            "report_id": manifest.get("report_id") or report_summary.get("report_id") or report_meta.get("report_id"),
        },
        "artifacts": {
            "report_path": artifacts.get("report_meta") or artifacts.get("report_markdown"),
            "snapshot_paths": snapshot_paths,
        },
        "timeframe": _timeframe(report_meta, manifest.get("requirement", ""), list(timeline)),
    }

    return ForecastV1.model_validate(payload)
