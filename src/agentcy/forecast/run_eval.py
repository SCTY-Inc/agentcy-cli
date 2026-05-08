"""Internal evaluation artifact for completed echo runs.

This artifact is intentionally repo-local and read-only. It summarizes the
shape of an already-completed simulation without widening the canonical
forecast protocol.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any

from agentcy.protocols.utils import load_json_optional

_load_json = load_json_optional


def _load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8").strip()


def _extract_thesis(report_meta: dict[str, Any], report_markdown: str) -> str | None:
    outline = dict(report_meta.get("outline") or {})
    summary = str(outline.get("summary") or "").strip()
    if summary:
        return summary

    match = re.search(r"\*\*Executive Summary:\*\*\s*(.+?)(?:\n\n|$)", report_markdown, re.DOTALL)
    if match:
        return " ".join(match.group(1).split())

    first_paragraph = next(
        (chunk.strip("#- ") for chunk in report_markdown.split("\n\n") if chunk.strip()),
        "",
    )
    return " ".join(first_paragraph.split()) if first_paragraph else None


def _load_action_log(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []

    actions: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        payload = line.strip()
        if not payload:
            continue
        try:
            parsed = json.loads(payload)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            actions.append(parsed)
    return actions


def _average_score(*values: float | None) -> float:
    present = [value for value in values if isinstance(value, (int, float))]
    if not present:
        return 0.0
    return round(sum(present) / len(present), 2)


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 2)


def _normalized_entropy(counter: Counter[str]) -> float | None:
    total = sum(counter.values())
    if total <= 0:
        return None
    if len(counter) <= 1:
        return 0.0

    entropy = 0.0
    for count in counter.values():
        probability = count / total
        entropy -= probability * math.log(probability)
    return round(entropy / math.log(len(counter)), 2)


def _configured_agent_names(config: dict[str, Any]) -> list[str]:
    return [
        str(item.get("entity_name") or "").strip()
        for item in config.get("agent_configs", [])
        if str(item.get("entity_name") or "").strip()
    ]


def _active_platforms(actions: list[dict[str, Any]], timeline: list[dict[str, Any]]) -> set[str]:
    platforms = {
        str(item.get("platform") or "").strip().lower()
        for item in actions
        if str(item.get("platform") or "").strip()
    }
    if platforms:
        return platforms

    inferred: set[str] = set()
    if any(int(item.get("twitter_actions", 0)) > 0 for item in timeline):
        inferred.add("twitter")
    if any(int(item.get("reddit_actions", 0)) > 0 for item in timeline):
        inferred.add("reddit")
    return inferred


def _configured_platform_count(config: dict[str, Any]) -> int:
    return int(bool(config.get("twitter_config"))) + int(bool(config.get("reddit_config")))


def _action_content(action: dict[str, Any]) -> str:
    action_args = action.get("action_args")
    if isinstance(action_args, dict):
        content = action_args.get("content")
        if isinstance(content, str):
            return content.strip()
    for key in ("content", "result"):
        value = action.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _critic_rejection_rate(
    actions: list[dict[str, Any]], configured_agents: set[str]
) -> tuple[float | None, int]:
    if not actions:
        return None, 0

    rejected = 0
    seen_content: set[tuple[str, str]] = set()
    for action in actions:
        agent_name = str(action.get("agent_name") or "").strip()
        normalized_agent = agent_name.casefold()
        content = " ".join(_action_content(action).split()).casefold()
        action_type = str(action.get("action_type") or "").strip().upper()
        success = action.get("success", True)

        should_reject = False
        if success is False:
            should_reject = True
        elif configured_agents and agent_name and agent_name not in configured_agents:
            should_reject = True
        elif action_type.startswith("CREATE_") and not content:
            should_reject = True
        elif content and (normalized_agent, content) in seen_content:
            should_reject = True

        if content:
            seen_content.add((normalized_agent, content))
        if should_reject:
            rejected += 1

    return round(rejected / len(actions), 2), rejected


def build_completed_run_eval(manifest: dict[str, Any], run_dir: str | Path) -> dict[str, Any]:
    if manifest.get("status") != "completed":
        raise ValueError("run eval export is only available for completed runs")

    run_path = Path(run_dir)
    timeline = _load_json(run_path / "simulation" / "timeline.json") or []
    top_agents = _load_json(run_path / "simulation" / "top_agents.json") or []
    simulation_config = _load_json(run_path / "simulation" / "config.json") or {}
    action_log = _load_action_log(run_path / "simulation" / "actions.jsonl")
    report_meta = _load_json(run_path / "report" / "meta.json") or {}
    report_markdown = _load_text(run_path / "report" / "report.md")
    imported_lineage = dict(manifest.get("imported_lineage") or {})
    artifacts = dict(manifest.get("artifacts") or {})

    total_rounds = len(timeline)
    active_rounds = sum(1 for item in timeline if int(item.get("total_actions", 0)) > 0)
    total_actions = sum(max(0, int(item.get("total_actions", 0))) for item in timeline)
    peak_round_actions = max((int(item.get("total_actions", 0)) for item in timeline), default=0)
    round_coverage_ratio = round(active_rounds / total_rounds, 2) if total_rounds else 0.0
    peak_round_share = round(peak_round_actions / total_actions, 2) if total_actions else 0.0

    active_agent_count = sum(1 for item in top_agents if int(item.get("total_actions", 0)) > 0)
    if action_log:
        active_agent_count = len(
            {
                str(item.get("agent_name") or "").strip()
                for item in action_log
                if str(item.get("agent_name") or "").strip()
            }
        )
    top_agent_actions = int(top_agents[0].get("total_actions", 0)) if top_agents else 0
    top_agent_share = round(top_agent_actions / total_actions, 2) if total_actions else 0.0
    top_agent_names = [
        str(item.get("agent_name") or "").strip()
        for item in top_agents[:3]
        if str(item.get("agent_name") or "").strip()
    ]
    configured_agents = _configured_agent_names(simulation_config)
    configured_agent_count = len(configured_agents)
    active_agent_coverage_ratio = _ratio(active_agent_count, configured_agent_count)
    active_platform_count = len(_active_platforms(action_log, timeline))
    platform_coverage_ratio = _ratio(
        active_platform_count,
        _configured_platform_count(simulation_config),
    )
    coverage_score = _average_score(
        round_coverage_ratio,
        active_agent_coverage_ratio,
        platform_coverage_ratio,
    )

    actor_diversity = None
    if action_log:
        actor_diversity = _normalized_entropy(
            Counter(
                str(item.get("agent_name") or "").strip()
                for item in action_log
                if str(item.get("agent_name") or "").strip()
            )
        )
    elif top_agents:
        actor_diversity = _normalized_entropy(
            Counter(
                {
                    str(item.get("agent_name") or "").strip(): int(item.get("total_actions", 0))
                    for item in top_agents
                    if str(item.get("agent_name") or "").strip() and int(item.get("total_actions", 0)) > 0
                }
            )
        )
    action_type_diversity = _normalized_entropy(
        Counter(
            str(item.get("action_type") or "").strip().upper()
            for item in action_log
            if str(item.get("action_type") or "").strip()
        )
    )
    local_diversity_score = _average_score(actor_diversity, action_type_diversity)

    event_config = dict(simulation_config.get("event_config") or {})
    narrative_load_score = None
    if simulation_config:
        narrative_load_score = round(
            min(
                (
                    len(event_config.get("initial_posts") or [])
                    + len(event_config.get("scheduled_events") or [])
                    + len(event_config.get("hot_topics") or [])
                )
                / 6,
                1.0,
            ),
            2,
        )
    action_type_variety = None
    if action_log:
        action_type_variety = round(
            min(
                len(
                    {
                        str(item.get("action_type") or "").strip().upper()
                        for item in action_log
                        if str(item.get("action_type") or "").strip()
                    }
                )
                / 4,
                1.0,
            ),
            2,
        )
    complexity_score = _average_score(
        action_type_variety,
        round_coverage_ratio,
        narrative_load_score,
    )

    critic_rejection_rate, critic_rejected_actions = _critic_rejection_rate(
        action_log,
        set(configured_agents),
    )

    snapshot_count = sum(
        1
        for key in artifacts
        if key in {"swarm_overview", "cluster_map", "timeline", "platform_split"}
    )
    thesis = _extract_thesis(report_meta, report_markdown)

    if peak_round_share >= 0.6:
        activity_pattern = "burst"
    elif round_coverage_ratio >= 0.67:
        activity_pattern = "sustained"
    else:
        activity_pattern = "mixed"

    if round_coverage_ratio < 0.5:
        coverage_note = "Conversation died out early relative to the simulated horizon."
    elif peak_round_share >= 0.6:
        coverage_note = "Most activity clustered into one round; follow-through was limited."
    else:
        coverage_note = "Attention stayed distributed across multiple rounds."

    risks: list[str] = []
    strengths: list[str] = []

    if round_coverage_ratio < 0.5:
        risks.append("attention faded early relative to the simulated run horizon")
    if peak_round_share >= 0.6:
        risks.append("one round dominated the simulated activity window")
    if top_agent_share >= 0.6:
        risks.append("one agent dominated the simulated activity mix")
    if coverage_score < 0.5:
        risks.append("synthetic coverage stayed narrow across the configured run space")
    if local_diversity_score < 0.4:
        risks.append("synthetic local diversity stayed narrow inside covered scenarios")
    if complexity_score < 0.35:
        risks.append("synthetic complexity stayed low relative to the configured prompt space")
    if isinstance(critic_rejection_rate, (int, float)) and critic_rejection_rate >= 0.25:
        risks.append("heuristic critic rejected a large share of simulated actions")

    if imported_lineage.get("brief_id"):
        strengths.append("run retains canonical brief lineage")
    if thesis:
        strengths.append("report thesis is available for downstream review")
    if snapshot_count > 0:
        strengths.append("visual snapshots are available for review")
    if coverage_score >= 0.75:
        strengths.append("simulation covered most configured agents and platforms")
    if local_diversity_score >= 0.7:
        strengths.append("simulation explored multiple local reaction variants")
    if isinstance(critic_rejection_rate, (int, float)) and critic_rejection_rate <= 0.1:
        strengths.append("heuristic critic accepted most simulated actions")

    return {
        "artifact_type": "echo.run_eval.v1",
        "schema_version": "v1",
        "run_id": manifest["run_id"],
        "brief_id": imported_lineage.get("brief_id"),
        "brand_id": imported_lineage.get("brand_id"),
        "generated_at": manifest.get("updated_at") or manifest.get("created_at"),
        "summary": {
            "activity_pattern": activity_pattern,
            "coverage_note": coverage_note,
            "thesis": thesis,
            "top_agents": top_agent_names,
        },
        "metrics": {
            "total_rounds": total_rounds,
            "active_rounds": active_rounds,
            "total_actions": total_actions,
            "round_coverage_ratio": round_coverage_ratio,
            "peak_round_share": peak_round_share,
            "active_agent_count": active_agent_count,
            "top_agent_share": top_agent_share,
            "configured_agent_count": configured_agent_count,
            "active_agent_coverage_ratio": active_agent_coverage_ratio,
            "active_platform_count": active_platform_count,
            "platform_coverage_ratio": platform_coverage_ratio,
            "coverage_score": coverage_score,
            "local_diversity_score": local_diversity_score,
            "complexity_score": complexity_score,
            "critic_rejection_rate": critic_rejection_rate,
            "critic_rejected_actions": critic_rejected_actions,
        },
        "inputs": {
            "source_file_count": len(manifest.get("source_files") or []),
            "has_brief_lineage": bool(imported_lineage.get("brief_id")),
        },
        "artifacts": {
            "snapshot_count": snapshot_count,
            "has_report_meta": bool(report_meta),
            "has_report_markdown": bool(report_markdown),
        },
        "risks": risks,
        "strengths": strengths,
    }
