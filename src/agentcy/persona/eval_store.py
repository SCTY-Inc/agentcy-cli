"""Persistence helpers for persona eval reports."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

EVALS_DIR = Path.home() / ".prsna" / "evals"


def default_eval_report_path(persona_name: str) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return EVALS_DIR / persona_name / f"{timestamp}.json"


def save_eval_report(persona_name: str, report: dict[str, Any]) -> Path:
    path = default_eval_report_path(persona_name)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(report)
    payload.setdefault("persona", persona_name)
    payload.setdefault("saved_at", datetime.now(timezone.utc).isoformat())
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_eval_report(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def list_eval_reports(persona_name: str, limit: int = 10) -> list[dict[str, Any]]:
    root = EVALS_DIR / persona_name
    if not root.exists():
        return []

    reports: list[dict[str, Any]] = []
    for path in sorted(root.glob("*.json"), reverse=True)[:limit]:
        payload = load_eval_report(path)
        reports.append(
            {
                "path": str(path),
                "persona": payload.get("persona", persona_name),
                "score": payload.get("score"),
                "difficulty": payload.get("difficulty"),
                "saved_at": payload.get("saved_at"),
            }
        )
    return reports


def latest_eval_report(persona_name: str) -> dict[str, Any] | None:
    reports = list_eval_reports(persona_name, limit=1)
    if not reports:
        return None

    latest_path = reports[0]["path"]
    payload = load_eval_report(latest_path)
    payload.setdefault("report_path", latest_path)
    return payload


def compare_latest_eval_reports(persona_name: str) -> dict[str, Any] | None:
    reports = list_eval_reports(persona_name, limit=2)
    if len(reports) < 2:
        return None

    latest = load_eval_report(reports[0]["path"])
    previous = load_eval_report(reports[1]["path"])

    latest_failure_modes = set(latest.get("failure_modes") or [])
    previous_failure_modes = set(previous.get("failure_modes") or [])

    def delta(field: str) -> float | None:
        latest_value = latest.get(field)
        previous_value = previous.get(field)
        if not isinstance(latest_value, (int, float)) or not isinstance(
            previous_value, (int, float)
        ):
            return None
        return round(latest_value - previous_value, 4)

    return {
        "persona": persona_name,
        "latest": {**latest, "report_path": reports[0]["path"]},
        "previous": {**previous, "report_path": reports[1]["path"]},
        "delta": {
            "score": delta("score"),
            "boundary_pass_rate": delta("boundary_pass_rate"),
        },
        "failure_modes": {
            "added": sorted(latest_failure_modes - previous_failure_modes),
            "removed": sorted(previous_failure_modes - latest_failure_modes),
            "unchanged": sorted(latest_failure_modes & previous_failure_modes),
        },
    }
