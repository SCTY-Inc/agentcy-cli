import argparse
import json
import sys
from pathlib import Path

import pytest


from agentcy.forecast.brief_v1 import import_brief_v1
from agentcy.forecast.cli import _refresh_run_manifest, _resolve_run_inputs, build_parser, main
from agentcy.forecast.forecast_v1 import build_completed_forecast_v1
from agentcy.forecast.config import Config
from agentcy.forecast.utils.oasis_llm import get_simulation_runtime_preflight
from agentcy.forecast.run_artifacts import RunStore
from agentcy.forecast.services.simulation_runner import RunnerStatus, SimulationRunState
from agentcy.forecast.visual_snapshots import generate_visual_snapshots


ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS = ROOT / "src" / "agentcy" / "protocols" / "examples"


def test_run_store_persists_manifest_and_frozen_inputs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))

    source_file = tmp_path / "seed.md"
    source_file.write_text("# Seed\n\nExample content", encoding="utf-8")

    store = RunStore()
    manifest = store.create(
        "Predict the reaction",
        [str(source_file)],
        project_name="Demo",
        brief_path=str(PROTOCOLS / "brief.v1.rich.json"),
        imported_lineage={"brief_id": "givecare.brief.demo", "brand_id": "givecare.brand.core"},
    )
    copied = store.freeze_source_files(manifest["run_id"], [str(source_file)])

    assert manifest["status"] == "created"
    assert len(copied) == 1
    assert Path(copied[0]).read_text(encoding="utf-8") == source_file.read_text(encoding="utf-8")

    updated = store.update(manifest["run_id"], status="graph_ready", graph_id="graph_demo")
    assert updated["graph_id"] == "graph_demo"
    assert updated["brief_path"].endswith("brief.v1.rich.json")
    assert updated["imported_lineage"]["brand_id"] == "givecare.brand.core"

    listed = store.list(limit=5)
    assert listed[0]["run_id"] == manifest["run_id"]


def test_generate_visual_snapshots_writes_svg_outputs(tmp_path: Path):
    graph_data = {
        "graph_id": "graph_demo",
        "node_count": 3,
        "edge_count": 2,
        "nodes": [
            {"uuid": "n1", "name": "Alice", "labels": ["Entity", "Citizen"]},
            {"uuid": "n2", "name": "Bob", "labels": ["Entity", "Citizen"]},
            {"uuid": "n3", "name": "University", "labels": ["Entity", "Institution"]},
        ],
        "edges": [
            {"source_node_uuid": "n1", "target_node_uuid": "n3"},
            {"source_node_uuid": "n2", "target_node_uuid": "n3"},
        ],
    }
    timeline = [
        {"round_num": 1, "twitter_actions": 3, "reddit_actions": 1, "total_actions": 4},
        {"round_num": 2, "twitter_actions": 2, "reddit_actions": 4, "total_actions": 6},
    ]

    artifacts = generate_visual_snapshots(graph_data, timeline, str(tmp_path / "visuals"))

    assert set(artifacts) == {"swarm_overview", "cluster_map", "timeline", "platform_split"}
    for path in artifacts.values():
        content = Path(path).read_text(encoding="utf-8")
        assert content.startswith("<svg")
        assert "font-family" in content


def test_generate_visual_snapshots_handles_empty_graph(tmp_path: Path):
    artifacts = generate_visual_snapshots({"nodes": [], "edges": []}, [], str(tmp_path / "visuals"))
    cluster_map = Path(artifacts["cluster_map"]).read_text(encoding="utf-8")

    assert "No graph nodes available" in cluster_map


def test_cli_parser_is_run_first():
    parser = build_parser()
    subparsers = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))

    assert set(subparsers.choices) == {"doctor", "run", "runs"}

    run_help = subparsers.choices["run"].format_help()
    assert "--files" in run_help
    assert "--requirement" in run_help
    assert "--brief" in run_help
    assert "--project-name" not in run_help
    assert "--additional-context" not in run_help
    assert "--parallel-profile-count" not in run_help
    assert "--no-llm-profiles" not in run_help
    assert "--enable-graph-memory-update" not in run_help

    runs_subparsers = next(
        action for action in subparsers.choices["runs"]._actions if isinstance(action, argparse._SubParsersAction)
    )
    assert set(runs_subparsers.choices) == {"list", "status", "export"}


def test_refresh_run_manifest_promotes_completed_simulation(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))

    store = RunStore()
    manifest = store.create("Predict reaction", [], project_name="Status Demo")
    store.update(
        manifest["run_id"],
        status="simulation_running",
        simulation_id="sim_123",
    )

    state = SimulationRunState(
        simulation_id="sim_123",
        runner_status=RunnerStatus.COMPLETED,
        current_round=4,
        total_rounds=4,
    )
    monkeypatch.setattr("agentcy.forecast.cli.SimulationRunner.get_run_state", lambda simulation_id: state)

    refreshed = _refresh_run_manifest(store, manifest["run_id"])

    assert refreshed["status"] == "simulation_completed"
    assert refreshed["task_progress"] == 100


def test_cli_doctor_emits_json(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(
        "agentcy.forecast.cli.get_simulation_runtime_preflight",
        lambda: {
            "ready": False,
            "python": {"current": "3.12.2", "supported": "3.11", "ready": False},
            "dependencies": {
                "simulation_extra_installed": False,
                "ready": False,
                "missing_import": "No module named 'camel'",
            },
            "error": "Simulation runtime is only supported on Python 3.11",
        },
    )

    exit_code = main(["doctor", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["command"] == "doctor"
    assert payload["ready"] is False
    assert payload["checks"]["python"]["supported"] == "3.11"
    assert payload["checks"]["dependencies"]["simulation_extra_installed"] is False



def test_cli_runs_list_and_status_emit_json(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))

    store = RunStore()
    manifest = store.create("Predict reaction", [], project_name="List Demo")
    store.update(manifest["run_id"], status="graph_ready", graph_id="graph_123")
    store.write_text(manifest["run_id"], "visuals/swarm-overview.svg", "<svg />")
    store.record_artifact(manifest["run_id"], "swarm_overview", "visuals/swarm-overview.svg")

    exit_code = main(["runs", "list", "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert payload["count"] == 1
    assert payload["runs"][0]["run_id"] == manifest["run_id"]

    exit_code = main(["runs", "status", manifest["run_id"], "--json"])
    captured = capsys.readouterr()
    status_payload = json.loads(captured.out)

    assert exit_code == 0
    assert status_payload["graph_id"] == "graph_123"
    assert status_payload["status"] == "graph_ready"

    exit_code = main(["runs", "export", manifest["run_id"], "--artifact", "swarm_overview", "--json"])
    captured = capsys.readouterr()
    export_payload = json.loads(captured.out)

    assert exit_code == 0
    assert export_payload["artifact"] == "swarm_overview"
    assert export_payload["path"].endswith("visuals/swarm-overview.svg")


def test_simulation_runtime_preflight_reports_python_and_dependency_readiness():
    ready = get_simulation_runtime_preflight(
        version_info=argparse.Namespace(major=3, minor=11, micro=9),
        camel_import_error=None,
    )
    assert ready["ready"] is True
    assert ready["python"]["ready"] is True
    assert ready["dependencies"]["simulation_extra_installed"] is True

    not_ready = get_simulation_runtime_preflight(
        version_info=argparse.Namespace(major=3, minor=12, micro=1),
        camel_import_error=ImportError("No module named 'camel'"),
    )
    assert not_ready["ready"] is False
    assert not_ready["python"]["ready"] is False
    assert not_ready["dependencies"]["simulation_extra_installed"] is False
    assert not_ready["error"] is not None



def test_import_brief_v1_derives_requirement_and_lineage():
    imported = import_brief_v1(PROTOCOLS / "brief.v1.rich.json")

    assert imported.brief.brief_id == "givecare.brief.fall-checkin.social-email.2026-04-12"
    assert imported.lineage == {
        "brief_id": "givecare.brief.fall-checkin.social-email.2026-04-12",
        "brand_id": "givecare.brand.core",
        "source_voice_pack_id": "givecare.voice.fall-checkin.v1",
        "campaign_id": "givecare.campaign.fall-checkin.2026q2",
        "signal_id": "givecare.signal.support-calls.fall-2026-04",
    }
    assert "Objective:" in imported.requirement
    assert "Model plausible public reaction" in imported.requirement
    assert imported.frozen_input["lineage"]["source_brief_id"] == imported.brief.brief_id


def test_resolve_run_inputs_prefers_brief_requirement(tmp_path: Path):
    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")

    args = argparse.Namespace(
        files=[str(source_file)],
        requirement=None,
        brief=str(PROTOCOLS / "brief.v1.rich.json"),
    )

    source_files, requirement, imported = _resolve_run_inputs(args)

    assert source_files == [str(source_file.resolve())]
    assert imported is not None
    assert requirement == imported.requirement


def test_resolve_run_inputs_rejects_missing_requirement_without_brief(tmp_path: Path):
    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")

    args = argparse.Namespace(files=[str(source_file)], requirement=None, brief=None)

    with pytest.raises(ValueError, match="--requirement is required unless --brief is supplied"):
        _resolve_run_inputs(args)


def test_import_brief_v1_rejects_malformed_json(tmp_path: Path):
    brief_path = tmp_path / "broken.json"
    brief_path.write_text("{not json", encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid brief.v1 JSON"):
        import_brief_v1(brief_path)


def test_import_brief_v1_rejects_missing_required_lineage_field(tmp_path: Path):
    payload = json.loads((PROTOCOLS / "brief.v1.rich.json").read_text(encoding="utf-8"))
    del payload["brief_id"]
    brief_path = tmp_path / "missing-brief-id.json"
    brief_path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="Invalid brief.v1 payload"):
        import_brief_v1(brief_path)


def test_build_completed_forecast_v1_separates_lineage_and_provenance(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))

    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")
    imported = import_brief_v1(PROTOCOLS / "brief.v1.rich.json")

    store = RunStore()
    manifest = store.create(
        imported.requirement,
        [str(source_file)],
        project_name="Forecast Demo",
        brief_path=str(PROTOCOLS / "brief.v1.rich.json"),
        imported_lineage=imported.lineage,
    )
    run_id = manifest["run_id"]

    store.write_json(run_id, "input/brief.v1.json", imported.brief.model_dump(exclude_none=True, by_alias=True))
    store.record_artifact(run_id, "brief_v1", "input/brief.v1.json")
    store.write_json(
        run_id,
        "report/meta.json",
        {
            "report_id": "miro.report.demo",
            "simulation_id": "miro.sim.demo",
            "graph_id": "miro.graph.demo",
            "simulation_requirement": imported.requirement,
            "completed_at": "2026-04-12T05:24:00Z",
            "outline": {
                "summary": "Families are most likely to respond to practical relief framing with one clear next step.",
            },
        },
    )
    store.record_artifact(run_id, "report_meta", "report/meta.json")
    store.write_json(
        run_id,
        "report/summary.json",
        {
            "run_id": run_id,
            "project_id": "miro.project.demo",
            "graph_id": "miro.graph.demo",
            "simulation_id": "miro.sim.demo",
            "report_id": "miro.report.demo",
        },
    )
    store.record_artifact(run_id, "report_summary", "report/summary.json")
    store.write_text(
        run_id,
        "report/report.md",
        "# Forecast\n\n**Executive Summary:** Families are most likely to respond to practical relief framing with one clear next step.",
    )
    store.record_artifact(run_id, "report_markdown", "report/report.md")
    store.write_json(
        run_id,
        "simulation/timeline.json",
        [
            {"round_num": 0, "total_actions": 8},
            {"round_num": 1, "total_actions": 2},
            {"round_num": 2, "total_actions": 0},
        ],
    )
    store.record_artifact(run_id, "timeline_json", "simulation/timeline.json")
    store.write_json(
        run_id,
        "simulation/top_agents.json",
        [
            {"agent_name": "Caregiver advocates", "total_actions": 4},
            {"agent_name": "Health systems", "total_actions": 3},
        ],
    )
    store.record_artifact(run_id, "top_agents", "simulation/top_agents.json")
    store.write_text(run_id, "visuals/swarm-overview.svg", "<svg />")
    store.record_artifact(run_id, "swarm_overview", "visuals/swarm-overview.svg")
    store.write_text(run_id, "visuals/timeline.svg", "<svg />")
    store.record_artifact(run_id, "timeline", "visuals/timeline.svg")

    manifest = store.update(
        run_id,
        status="completed",
        project_id="miro.project.demo",
        graph_id="miro.graph.demo",
        simulation_id="miro.sim.demo",
        report_id="miro.report.demo",
    )

    forecast = build_completed_forecast_v1(manifest, store.run_dir(run_id)).model_dump(exclude_none=True)

    assert forecast["artifact_type"] == "forecast.v1"
    assert forecast["brief_id"] == imported.brief.brief_id
    assert forecast["brand_id"] == imported.brief.brand_id
    assert forecast["lineage"] == {
        "source_brief_id": imported.brief.brief_id,
        "source_voice_pack_id": imported.brief.voice_pack_id,
        "campaign_id": imported.lineage["campaign_id"],
        "signal_id": imported.lineage["signal_id"],
    }
    assert forecast["provenance"] == {
        "project_id": "miro.project.demo",
        "graph_id": "miro.graph.demo",
        "simulation_id": "miro.sim.demo",
        "report_id": "miro.report.demo",
    }
    assert "forecast_id" in forecast and forecast["forecast_id"].startswith("givecare.brand.core.forecast.")
    assert forecast["artifacts"]["report_path"] == "report/meta.json"
    assert forecast["artifacts"]["snapshot_paths"] == ["visuals/swarm-overview.svg", "visuals/timeline.svg"]
    assert forecast["summary"]["recommended_action"].startswith("Lead with")
    assert len(forecast["scenarios"]) >= 1


def test_runs_export_emits_forecast_v1_for_completed_brief_based_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))

    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")
    imported = import_brief_v1(PROTOCOLS / "brief.v1.rich.json")

    store = RunStore()
    manifest = store.create(
        imported.requirement,
        [str(source_file)],
        project_name="Export Demo",
        brief_path=str(PROTOCOLS / "brief.v1.rich.json"),
        imported_lineage=imported.lineage,
    )
    run_id = manifest["run_id"]
    store.write_json(run_id, "input/brief.v1.json", imported.brief.model_dump(exclude_none=True, by_alias=True))
    store.record_artifact(run_id, "brief_v1", "input/brief.v1.json")
    store.write_json(
        run_id,
        "report/meta.json",
        {
            "report_id": "miro.report.export",
            "simulation_id": "miro.sim.export",
            "graph_id": "miro.graph.export",
            "simulation_requirement": imported.requirement,
            "completed_at": "2026-04-12T05:24:00Z",
            "outline": {"summary": "Practical caregiver relief is the strongest message."},
        },
    )
    store.record_artifact(run_id, "report_meta", "report/meta.json")
    store.write_json(run_id, "report/summary.json", {"report_id": "miro.report.export"})
    store.record_artifact(run_id, "report_summary", "report/summary.json")
    store.write_json(run_id, "simulation/timeline.json", [{"round_num": 0, "total_actions": 5}])
    store.record_artifact(run_id, "timeline_json", "simulation/timeline.json")
    store.write_json(run_id, "simulation/top_agents.json", [{"agent_name": "Caregivers", "total_actions": 5}])
    store.record_artifact(run_id, "top_agents", "simulation/top_agents.json")
    store.update(
        run_id,
        status="completed",
        project_id="miro.project.export",
        graph_id="miro.graph.export",
        simulation_id="miro.sim.export",
        report_id="miro.report.export",
    )

    exit_code = main(["runs", "export", run_id, "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert "forecast_v1" in payload["artifacts"]

    forecast_path = Path(payload["artifacts"]["forecast_v1"])
    forecast_payload = json.loads(forecast_path.read_text(encoding="utf-8"))

    assert forecast_payload["artifact_type"] == "forecast.v1"
    assert forecast_payload["lineage"]["source_brief_id"] == imported.brief.brief_id
    assert forecast_payload["provenance"]["simulation_id"] == "miro.sim.export"


def test_runs_export_does_not_emit_forecast_v1_for_failed_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))

    store = RunStore()
    manifest = store.create("Predict reaction", [], project_name="Failed Demo")
    store.update(manifest["run_id"], status="failed", error="boom")

    exit_code = main(["runs", "export", manifest["run_id"], "--json"])
    captured = capsys.readouterr()
    payload = json.loads(captured.out)

    assert exit_code == 0
    assert "forecast_v1" not in payload["artifacts"]
