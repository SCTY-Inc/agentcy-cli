"""Deterministic smoke-mode outputs for echo runs.

Smoke mode keeps the CLI and artifact flow intact while skipping the live OASIS
runtime. It relies on the already-prepared simulation config and produces a
small, reproducible simulation timeline, agent summary, and report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agentcy_protocols.utils import load_json


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass
class SmokeAction:
    timestamp: str
    platform: str
    actor: str
    action_type: str
    content: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "platform": self.platform,
            "actor": self.actor,
            "action_type": self.action_type,
            "content": self.content,
        }


_load_json = load_json


def _agent_names(config: dict[str, Any]) -> list[str]:
    names = [
        str(item.get("entity_name") or "").strip()
        for item in config.get("agent_configs", [])
        if str(item.get("entity_name") or "").strip()
    ]
    return names or ["Audience", "Advocates", "Brand"]


def build_smoke_outputs(
    sim_dir: str | Path,
    *,
    run_id: str,
    simulation_id: str,
    graph_id: str,
    requirement: str,
    platform: str,
    max_rounds: int | None = None,
) -> dict[str, Any]:
    config = _load_json(Path(sim_dir) / "simulation_config.json")
    agent_names = _agent_names(config)
    round_count = max(1, min(max_rounds or 2, 3))

    timeline: list[dict[str, Any]] = []
    for round_num in range(round_count):
        total_actions = max(len(agent_names) - round_num, 1)
        if platform == "reddit":
            timeline.append(
                {
                    "round_num": round_num,
                    "twitter_actions": 0,
                    "reddit_actions": total_actions,
                    "total_actions": total_actions,
                }
            )
        elif platform == "parallel":
            twitter_actions = max(total_actions - 1, 1)
            reddit_actions = 1 if total_actions > 1 else 0
            timeline.append(
                {
                    "round_num": round_num,
                    "twitter_actions": twitter_actions,
                    "reddit_actions": reddit_actions,
                    "total_actions": twitter_actions + reddit_actions,
                }
            )
        else:
            timeline.append(
                {
                    "round_num": round_num,
                    "twitter_actions": total_actions,
                    "reddit_actions": 0,
                    "total_actions": total_actions,
                }
            )

    agent_stats = [
        {"agent_name": name, "total_actions": max(len(agent_names) - index, 1)}
        for index, name in enumerate(agent_names)
    ]

    platform_label = "parallel" if platform == "parallel" else platform
    actions = [
        SmokeAction(
            timestamp=_now(),
            platform=platform_label,
            actor=agent_names[0],
            action_type="CREATE_POST",
            content="Smoke-mode kickoff post generated from prepared simulation config.",
        )
    ]
    if len(agent_names) > 1:
        actions.append(
            SmokeAction(
                timestamp=_now(),
                platform=platform_label,
                actor=agent_names[1],
                action_type="CREATE_COMMENT",
                content="Follow-up reaction captured in smoke mode.",
            )
        )

    thesis = (
        "Smoke-mode forecast: attention is likely to center on practical relief, "
        "questions about scale, and whether the support can last beyond the pilot."
    )
    report_payload = {
        "report_id": f"smoke.report.{run_id}",
        "simulation_id": simulation_id,
        "graph_id": graph_id,
        "completed_at": _now(),
        "simulation_requirement": requirement,
        "outline": {"summary": thesis},
        "smoke_mode": True,
    }
    report_markdown = (
        "# Smoke Report\n\n"
        f"**Executive Summary:** {thesis}\n\n"
        "This report was generated from smoke mode after ontology, graph, and "
        "profile preparation completed successfully."
    )

    return {
        "timeline": timeline,
        "agent_stats": agent_stats,
        "actions": actions,
        "report_payload": report_payload,
        "report_markdown": report_markdown,
    }
