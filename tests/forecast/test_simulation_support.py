from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest


from agentcy.forecast.config import Config
from agentcy.forecast.tools.simulation_support import check_simulation_prepared


@pytest.fixture
def simulation_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "simulations"
    root.mkdir()
    monkeypatch.setattr(Config, "OASIS_SIMULATION_DATA_DIR", str(root))
    return root


def write_required_files(simulation_dir: Path, *, status: str = "ready", config_generated: bool = True) -> None:
    simulation_dir.mkdir(parents=True, exist_ok=True)
    (simulation_dir / "state.json").write_text(
        json.dumps(
            {
                "status": status,
                "config_generated": config_generated,
                "entities_count": 3,
                "entity_types": ["Person"],
            }
        ),
        encoding="utf-8",
    )
    (simulation_dir / "simulation_config.json").write_text("{}", encoding="utf-8")
    (simulation_dir / "reddit_profiles.json").write_text("[]", encoding="utf-8")
    (simulation_dir / "twitter_profiles.csv").write_text("id,name\n1,alice\n", encoding="utf-8")


def test_check_simulation_prepared_marks_preparing_runs_ready(simulation_root: Path):
    simulation_dir = simulation_root / "sim-123"
    write_required_files(simulation_dir, status="preparing")

    prepared, details = check_simulation_prepared("sim-123")

    assert prepared is True
    assert details["status"] == "ready"
    persisted = json.loads((simulation_dir / "state.json").read_text(encoding="utf-8"))
    assert persisted["status"] == "ready"
    assert "updated_at" in persisted


def test_check_simulation_prepared_reports_invalid_state_json(simulation_root: Path):
    simulation_dir = simulation_root / "sim-bad"
    simulation_dir.mkdir(parents=True, exist_ok=True)
    (simulation_dir / "state.json").write_text("{not-json", encoding="utf-8")
    (simulation_dir / "simulation_config.json").write_text("{}", encoding="utf-8")
    (simulation_dir / "reddit_profiles.json").write_text("[]", encoding="utf-8")
    (simulation_dir / "twitter_profiles.csv").write_text("id,name\n1,alice\n", encoding="utf-8")

    prepared, details = check_simulation_prepared("sim-bad")

    assert prepared is False
    assert details["reason"].startswith("Failed to read state file:")
