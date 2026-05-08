from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


from agentcy.forecast.services.simulation_runner import RunnerStatus, SimulationRunState, SimulationRunner


def test_load_run_state_returns_none_for_invalid_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    simulation_id = "sim-invalid"
    sim_dir = tmp_path / simulation_id
    sim_dir.mkdir(parents=True)
    (sim_dir / "run_state.json").write_text("{not-json", encoding="utf-8")

    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))

    assert SimulationRunner._load_run_state(simulation_id) is None


def test_read_action_log_ignores_invalid_and_non_object_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    simulation_id = "sim-actions"
    sim_dir = tmp_path / simulation_id / "twitter"
    sim_dir.mkdir(parents=True)
    log_path = sim_dir / "actions.jsonl"
    log_path.write_text(
        "\n".join(
            [
                "{bad json",
                json.dumps(["not", "an", "object"]),
                json.dumps({"event_type": "round_end", "round": 2, "simulated_hours": 4}),
                json.dumps(
                    {
                        "round": 2,
                        "timestamp": "2026-01-01T00:00:00Z",
                        "agent_id": 7,
                        "agent_name": "Alice",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "hello"},
                        "result": "ok",
                        "success": True,
                    }
                ),
            ]
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    state = SimulationRunState(simulation_id=simulation_id, runner_status=RunnerStatus.RUNNING)

    position = SimulationRunner._read_action_log(str(log_path), 0, state, "twitter")

    assert position == log_path.stat().st_size
    assert state.current_round == 2
    assert state.twitter_simulated_hours == 4
    assert len(state.recent_actions) == 1
    assert state.recent_actions[0].agent_name == "Alice"
    assert state.recent_actions[0].action_type == "CREATE_POST"
