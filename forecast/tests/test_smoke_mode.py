import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agentcy_forecast.cli import app
from agentcy_forecast.smoke_mode import build_smoke_outputs


def test_cli_run_includes_smoke_flag() -> None:
    from typer.testing import CliRunner
    result = CliRunner().invoke(app, ["run", "--help"])
    assert "--smoke" in result.output


def test_build_smoke_outputs_uses_prepared_simulation_config(tmp_path: Path) -> None:
    sim_dir = tmp_path / "sim"
    sim_dir.mkdir()
    (sim_dir / "simulation_config.json").write_text(
        json.dumps(
            {
                "agent_configs": [
                    {"entity_name": "Caregivers"},
                    {"entity_name": "Advocates"},
                    {"entity_name": "Nonprofit"},
                ]
            }
        ),
        encoding="utf-8",
    )

    payload = build_smoke_outputs(
        sim_dir,
        run_id="run_demo",
        simulation_id="sim_demo",
        graph_id="graph_demo",
        requirement="Predict reaction over the first week",
        platform="twitter",
        max_rounds=1,
    )

    assert len(payload["timeline"]) == 1
    assert payload["timeline"][0]["twitter_actions"] >= 1
    assert payload["agent_stats"][0]["agent_name"] == "Caregivers"
    assert payload["report_payload"]["smoke_mode"] is True
    assert "Executive Summary" in payload["report_markdown"]
