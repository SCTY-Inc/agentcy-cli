import json
import sys
from pathlib import Path

import pytest


from agentcy.forecast.services.simulation_runner import SimulationRunner


class _FakeProcess:
    def __init__(self):
        self.pid = 12345
        self.returncode = None

    def poll(self):
        return None


class _FakeThread:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def start(self):
        return None


def test_start_simulation_appends_no_wait_when_requested(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sim_id = "sim_demo"
    sim_dir = tmp_path / sim_id
    sim_dir.mkdir(parents=True)
    (sim_dir / "simulation_config.json").write_text(
        json.dumps(
            {
                "time_config": {"total_simulation_hours": 24, "minutes_per_round": 60},
                "agent_configs": [],
            }
        ),
        encoding="utf-8",
    )
    script_path = tmp_path / "run_twitter_simulation.py"
    script_path.write_text("print('ok')\n", encoding="utf-8")

    captured: dict[str, list[str]] = {}

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        return _FakeProcess()

    monkeypatch.setattr(SimulationRunner, "RUN_STATE_DIR", str(tmp_path))
    monkeypatch.setattr(SimulationRunner, "SCRIPTS_DIR", str(tmp_path))
    monkeypatch.setattr(
        SimulationRunner,
        "get_run_state",
        classmethod(lambda cls, simulation_id: None),
    )
    monkeypatch.setattr("agentcy.forecast.services.simulation_runner.subprocess.Popen", fake_popen)
    monkeypatch.setattr("agentcy.forecast.services.simulation_runner.threading.Thread", _FakeThread)

    state = SimulationRunner.start_simulation(
        sim_id,
        platform="twitter",
        max_rounds=1,
        wait_for_commands=False,
    )

    assert state.process_pid == 12345
    assert "--no-wait" in captured["cmd"]
