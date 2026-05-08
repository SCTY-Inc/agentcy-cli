from __future__ import annotations

import json
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS_DIR = ROOT / "src" / "agentcy" / "protocols"
EXAMPLES_DIR = PROTOCOLS_DIR / "examples"
BRAND_OS_DIR = ROOT / "tests" / "fixtures"


from agentcy.forecast.brief_v1 import import_brief_v1  # noqa: E402
from agentcy.forecast.cli import main  # noqa: E402
from agentcy.forecast.config import Config  # noqa: E402
from agentcy.forecast.run_artifacts import RunStore  # noqa: E402


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _seed_completed_brief_run(store: RunStore, brief_path: Path, source_file: Path) -> str:
    imported = import_brief_v1(brief_path)
    manifest = store.create(
        imported.requirement,
        [str(source_file)],
        project_name="Protocol Forecast Validation",
        brief_path=str(brief_path),
        imported_lineage=imported.lineage,
    )
    run_id = manifest["run_id"]

    store.write_json(run_id, "input/brief.v1.json", imported.brief.model_dump(exclude_none=True, by_alias=True))
    store.record_artifact(run_id, "brief_v1", "input/brief.v1.json")
    store.write_json(run_id, "input/brief_lineage.json", imported.frozen_input)
    store.record_artifact(run_id, "brief_lineage", "input/brief_lineage.json")

    store.write_json(
        run_id,
        "report/meta.json",
        {
            "report_id": "miro.report.protocol-handoff",
            "simulation_id": "miro.sim.protocol-handoff",
            "graph_id": "miro.graph.protocol-handoff",
            "simulation_requirement": imported.requirement,
            "completed_at": "2026-04-12T05:24:00Z",
            "outline": {
                "summary": "Caregivers are most likely to respond to practical relief framing with one clear next step.",
            },
        },
    )
    store.record_artifact(run_id, "report_meta", "report/meta.json")
    store.write_json(
        run_id,
        "report/summary.json",
        {
            "run_id": run_id,
            "project_id": "miro.project.protocol-handoff",
            "graph_id": "miro.graph.protocol-handoff",
            "simulation_id": "miro.sim.protocol-handoff",
            "report_id": "miro.report.protocol-handoff",
        },
    )
    store.record_artifact(run_id, "report_summary", "report/summary.json")
    store.write_text(
        run_id,
        "report/report.md",
        "# Forecast\n\n**Executive Summary:** Caregivers are most likely to respond to practical relief framing with one clear next step.",
    )
    store.record_artifact(run_id, "report_markdown", "report/report.md")
    store.write_json(
        run_id,
        "simulation/timeline.json",
        [
            {"round_num": 0, "total_actions": 7},
            {"round_num": 1, "total_actions": 3},
        ],
    )
    store.record_artifact(run_id, "timeline_json", "simulation/timeline.json")
    store.write_json(
        run_id,
        "simulation/top_agents.json",
        [
            {"agent_name": "Caregiver advocates", "total_actions": 5},
            {"agent_name": "Health systems", "total_actions": 3},
        ],
    )
    store.record_artifact(run_id, "top_agents", "simulation/top_agents.json")
    store.write_text(run_id, "visuals/swarm-overview.svg", "<svg />")
    store.record_artifact(run_id, "swarm_overview", "visuals/swarm-overview.svg")
    store.write_text(run_id, "visuals/timeline.svg", "<svg />")
    store.record_artifact(run_id, "timeline", "visuals/timeline.svg")

    store.update(
        run_id,
        status="completed",
        project_id="miro.project.protocol-handoff",
        graph_id="miro.graph.protocol-handoff",
        simulation_id="miro.sim.protocol-handoff",
        report_id="miro.report.protocol-handoff",
    )
    return run_id


def test_canonical_brief_to_forecast_handoff_validates_schema_and_lineage(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))

    schema = _load_json(PROTOCOLS_DIR / "schemas" / "forecast.v1.schema.json")
    validator = Draft202012Validator(schema)
    brief = _load_json(EXAMPLES_DIR / "brief.v1.rich.json")

    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")

    store = RunStore()
    run_id = _seed_completed_brief_run(store, EXAMPLES_DIR / "brief.v1.rich.json", source_file)

    exit_code = main(["runs", "export", run_id, "--artifact", "forecast_v1", "--json"])
    assert exit_code == 0

    forecast_rel_path = store.load(run_id)["artifacts"]["forecast_v1"]
    forecast_path = Path(store.run_dir(run_id)) / forecast_rel_path
    forecast = _load_json(forecast_path)
    validator.validate(forecast)

    assert forecast["artifact_type"] == "forecast.v1"
    assert forecast["writer"] == {"repo": "cli-mirofish", "module": "agentcy-echo"}
    assert forecast["brief_id"] == brief["brief_id"]
    assert forecast["brand_id"] == brief["brand_id"]
    assert forecast["lineage"]["source_brief_id"] == brief["brief_id"]
    assert forecast["lineage"]["source_voice_pack_id"] == brief["lineage"]["source_voice_pack_id"]
    assert forecast["lineage"]["campaign_id"] == brief["lineage"]["campaign_id"]
    assert forecast["lineage"]["signal_id"] == brief["lineage"]["signal_id"]

    assert forecast["provenance"] == {
        "project_id": "miro.project.protocol-handoff",
        "graph_id": "miro.graph.protocol-handoff",
        "simulation_id": "miro.sim.protocol-handoff",
        "report_id": "miro.report.protocol-handoff",
    }
    assert set(forecast["lineage"]).isdisjoint(forecast["provenance"])
    assert forecast["provenance"]["project_id"] != forecast["brand_id"]
    assert forecast["provenance"]["simulation_id"] != forecast["forecast_id"]


def test_brand_os_mirror_brief_also_round_trips_through_forecast_export(tmp_path, monkeypatch):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))

    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")

    store = RunStore()
    mirror_path = BRAND_OS_DIR / "brief.v1.rich.mirror.json"
    run_id = _seed_completed_brief_run(store, mirror_path, source_file)

    exit_code = main(["runs", "export", run_id, "--artifact", "forecast_v1", "--json"])
    assert exit_code == 0

    forecast_rel_path = store.load(run_id)["artifacts"]["forecast_v1"]
    forecast_path = Path(store.run_dir(run_id)) / forecast_rel_path
    forecast = _load_json(forecast_path)
    brief = _load_json(mirror_path)

    assert forecast["brief_id"] == brief["brief_id"]
    assert forecast["brand_id"] == brief["brand_id"]
    assert forecast["lineage"]["source_brief_id"] == brief["brief_id"]
    assert forecast["lineage"]["source_voice_pack_id"] == brief["lineage"]["source_voice_pack_id"]
    assert forecast["lineage"]["campaign_id"] == brief["lineage"]["campaign_id"]
    assert forecast["lineage"]["signal_id"] == brief["lineage"]["signal_id"]
