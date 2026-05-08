from __future__ import annotations

from pathlib import Path
from typing import Any

from agentcy.protocols.utils import load_json

WORKSPACE_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_FORECAST_PATH = (
    WORKSPACE_ROOT / "protocols" / "examples" / "forecast.v1.completed-rich.json"
)
CANONICAL_PERFORMANCE_PATH = WORKSPACE_ROOT / "protocols" / "examples" / "performance.v1.rich.json"

METRIC_ALIASES = {
    "engagement rate": "engagement_rate",
    "engagement_rate": "engagement_rate",
    "click-through rate": "ctr",
    "click through rate": "ctr",
    "ctr": "ctr",
    "impressions": "impressions",
    "reach": "reach",
    "engagements": "engagements",
    "reactions": "reactions",
    "likes": "likes",
    "comments": "comments",
    "shares": "shares",
    "saves": "saves",
    "clicks": "clicks",
    "video views": "video_views",
    "video_views": "video_views",
}


_load_json = load_json


def run_doctor_checks() -> list[dict[str, Any]]:
    return [
        {
            "name": "protocols-directory",
            "ok": (WORKSPACE_ROOT / "protocols").is_dir(),
            "path": str(WORKSPACE_ROOT / "protocols"),
        },
        {
            "name": "canonical-forecast-fixture",
            "ok": CANONICAL_FORECAST_PATH.is_file(),
            "path": str(CANONICAL_FORECAST_PATH),
        },
        {
            "name": "canonical-performance-fixture",
            "ok": CANONICAL_PERFORMANCE_PATH.is_file(),
            "path": str(CANONICAL_PERFORMANCE_PATH),
        },
    ]


def build_calibration_report(
    forecast_path: Path | str = CANONICAL_FORECAST_PATH,
    performance_path: Path | str = CANONICAL_PERFORMANCE_PATH,
) -> dict[str, Any]:
    forecast = _load_json(forecast_path)
    performance = _load_json(performance_path)

    _validate_lineage_match(forecast, performance)

    top_scenario = max(forecast["scenarios"], key=lambda scenario: scenario["probability"])
    metric_leaders = _metric_leaders(performance["observations"])
    focus = _extract_forecast_focus(forecast, performance["observations"])
    matched_metrics, missed_metrics = _score_alignment(focus, metric_leaders)
    verdict = _classify_alignment(focus, matched_metrics, missed_metrics)

    return {
        "forecast_id": forecast["forecast_id"],
        "performance_id": performance["performance_id"],
        "brief_id": forecast["brief_id"],
        "brand_id": forecast["brand_id"],
        "top_scenario": {
            "scenario_id": top_scenario["scenario_id"],
            "label": top_scenario["label"],
            "probability": top_scenario["probability"],
        },
        "forecast_focus": focus,
        "metric_leaders": metric_leaders,
        "alignment": {
            "verdict": verdict,
            "matched_metrics": matched_metrics,
            "missed_metrics": missed_metrics,
        },
        "recommendation": _recommendation(verdict, matched_metrics, missed_metrics),
    }


def _validate_lineage_match(forecast: dict[str, Any], performance: dict[str, Any]) -> None:
    for field in ("brief_id", "brand_id"):
        if forecast.get(field) != performance.get(field):
            raise ValueError(
                f"{field} mismatch between forecast ({forecast.get(field)!r}) "
                f"and performance ({performance.get(field)!r})"
            )


def _metric_leaders(observations: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    leaders: dict[str, dict[str, Any]] = {}
    for observation in observations:
        platform = observation["platform"]
        for metric, value in observation.get("metrics", {}).items():
            if not isinstance(value, (int, float)):
                continue
            current = leaders.get(metric)
            if current is None or value > current["value"]:
                leaders[metric] = {"platform": platform, "value": value}
    return leaders


def _extract_forecast_focus(
    forecast: dict[str, Any],
    observations: list[dict[str, Any]],
) -> dict[str, list[str]]:
    summary = forecast["summary"]
    text = " ".join(
        value for value in [summary.get("thesis"), summary.get("recommended_action")] if value
    ).lower()

    platform_mentions: list[str] = []
    for platform in [observation["platform"] for observation in observations]:
        if platform.lower() in text and platform not in platform_mentions:
            platform_mentions.append(platform)

    metric_mentions: list[str] = []
    for phrase, canonical_metric in METRIC_ALIASES.items():
        if phrase in text and canonical_metric not in metric_mentions:
            metric_mentions.append(canonical_metric)

    return {
        "platform_mentions": platform_mentions,
        "metric_mentions": metric_mentions,
    }


def _score_alignment(
    focus: dict[str, list[str]],
    metric_leaders: dict[str, dict[str, Any]],
) -> tuple[list[str], list[str]]:
    platforms = set(focus["platform_mentions"])
    matched_metrics: list[str] = []
    missed_metrics: list[str] = []

    for metric in focus["metric_mentions"]:
        leader = metric_leaders.get(metric)
        if leader is not None and leader["platform"] in platforms:
            matched_metrics.append(metric)
        else:
            missed_metrics.append(metric)

    return matched_metrics, missed_metrics


def _classify_alignment(
    focus: dict[str, list[str]],
    matched_metrics: list[str],
    missed_metrics: list[str],
) -> str:
    if not focus["platform_mentions"] or not focus["metric_mentions"]:
        return "unscored"
    if matched_metrics and not missed_metrics:
        return "aligned"
    if matched_metrics and missed_metrics:
        return "mixed"
    return "misaligned"


def _recommendation(verdict: str, matched_metrics: list[str], missed_metrics: list[str]) -> str:
    if verdict == "aligned":
        return (
            "Promote the forecast thesis into the next experiment and preserve "
            "the winning platform emphasis."
        )
    if verdict == "mixed":
        matched = ", ".join(matched_metrics)
        missed = ", ".join(missed_metrics)
        return (
            "Keep the core thesis but rerun the next experiment with metric-specific follow-up: "
            f"matched {matched}; missed {missed}."
        )
    if verdict == "misaligned":
        return (
            "Do not promote the forecast thesis unchanged; inspect the scenario "
            "assumptions before the next run."
        )
    return (
        "Forecast text did not name both a platform and measurable metric, so "
        "use this report as a human review aid only."
    )
