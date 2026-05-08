from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentcy.forecast.cli import main
from agentcy.forecast.config import Config
from agentcy.forecast.run_artifacts import RunStore
from agentcy.forecast.run_eval import build_completed_run_eval


def test_build_completed_run_eval_summarizes_existing_simulation_shape(tmp_path: Path):
    store = RunStore(root_dir=str(tmp_path / "runs"))
    manifest = store.create("Predict reaction", [], project_name="Eval Demo")
    run_id = manifest["run_id"]

    store.write_json(
        run_id,
        "simulation/timeline.json",
        [
            {"round_num": 0, "total_actions": 8},
            {"round_num": 1, "total_actions": 2},
            {"round_num": 2, "total_actions": 0},
        ],
    )
    store.write_json(
        run_id,
        "simulation/top_agents.json",
        [
            {"agent_name": "Caregivers", "total_actions": 6},
            {"agent_name": "Advocates", "total_actions": 4},
        ],
    )

    manifest = store.update(
        run_id,
        status="completed",
        imported_lineage={"brief_id": "brief.demo", "brand_id": "brand.demo"},
    )

    payload = build_completed_run_eval(manifest, store.run_dir(run_id))

    assert payload["artifact_type"] == "echo.run_eval.v1"
    assert payload["brief_id"] == "brief.demo"
    assert payload["brand_id"] == "brand.demo"
    assert payload["summary"]["activity_pattern"] == "burst"
    assert payload["metrics"]["round_coverage_ratio"] == 0.67
    assert payload["metrics"]["top_agent_share"] == 0.6


def test_build_completed_run_eval_includes_existing_report_and_artifact_context(
    tmp_path: Path,
):
    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")

    store = RunStore(root_dir=str(tmp_path / "runs"))
    manifest = store.create(
        "Predict reaction",
        [str(source_file)],
        project_name="Eval Context",
        imported_lineage={"brief_id": "brief.demo", "brand_id": "brand.demo"},
    )
    run_id = manifest["run_id"]

    store.write_json(
        run_id,
        "simulation/timeline.json",
        [
            {"round_num": 0, "total_actions": 8},
            {"round_num": 1, "total_actions": 0},
        ],
    )
    store.write_json(
        run_id,
        "simulation/top_agents.json",
        [
            {"agent_name": "Caregivers", "total_actions": 7},
            {"agent_name": "Advocates", "total_actions": 1},
        ],
    )
    store.write_json(
        run_id,
        "report/meta.json",
        {"outline": {"summary": "Practical caregiver relief is the strongest message."}},
    )
    store.record_artifact(run_id, "report_meta", "report/meta.json")
    store.write_text(run_id, "report/report.md", "# Forecast\n\nPractical caregiver relief wins.")
    store.record_artifact(run_id, "report_markdown", "report/report.md")
    store.write_text(run_id, "visuals/timeline.svg", "<svg />")
    store.record_artifact(run_id, "timeline", "visuals/timeline.svg")

    manifest = store.update(run_id, status="completed")
    payload = build_completed_run_eval(manifest, store.run_dir(run_id))

    assert payload["summary"]["thesis"] == "Practical caregiver relief is the strongest message."
    assert payload["summary"]["top_agents"] == ["Caregivers", "Advocates"]
    assert payload["inputs"] == {"source_file_count": 1, "has_brief_lineage": True}
    assert payload["artifacts"] == {
        "snapshot_count": 1,
        "has_report_meta": True,
        "has_report_markdown": True,
    }
    assert "one agent dominated the simulated activity mix" in payload["risks"]
    assert "visual snapshots are available for review" in payload["strengths"]


def test_build_completed_run_eval_computes_synthetic_quality_metrics_from_actions(
    tmp_path: Path,
):
    store = RunStore(root_dir=str(tmp_path / "runs"))
    manifest = store.create("Predict reaction", [], project_name="Eval Metrics")
    run_id = manifest["run_id"]

    store.write_json(
        run_id,
        "simulation/timeline.json",
        [
            {"round_num": 0, "twitter_actions": 1, "reddit_actions": 1, "total_actions": 2},
            {"round_num": 1, "twitter_actions": 1, "reddit_actions": 1, "total_actions": 2},
            {"round_num": 2, "twitter_actions": 0, "reddit_actions": 0, "total_actions": 0},
        ],
    )
    store.write_json(
        run_id,
        "simulation/top_agents.json",
        [
            {"agent_name": "Alice", "total_actions": 2},
            {"agent_name": "Bob", "total_actions": 1},
            {"agent_name": "Cara", "total_actions": 1},
        ],
    )
    store.write_json(
        run_id,
        "simulation/config.json",
        {
            "agent_configs": [
                {"agent_id": 1, "entity_name": "Alice"},
                {"agent_id": 2, "entity_name": "Bob"},
                {"agent_id": 3, "entity_name": "Cara"},
                {"agent_id": 4, "entity_name": "Dylan"},
            ],
            "event_config": {
                "initial_posts": [{"id": "seed"}],
                "scheduled_events": [{"id": "follow-up"}],
                "hot_topics": ["caregiver relief", "pilot durability"],
            },
            "twitter_config": {"platform": "twitter"},
            "reddit_config": {"platform": "reddit"},
        },
    )
    store.write_text(
        run_id,
        "simulation/actions.jsonl",
        "\n".join(
            [
                json.dumps(
                    {
                        "round_num": 0,
                        "timestamp": "2026-04-12T00:00:00Z",
                        "platform": "twitter",
                        "agent_id": 1,
                        "agent_name": "Alice",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "Need caregiver relief."},
                        "success": True,
                    }
                ),
                json.dumps(
                    {
                        "round_num": 0,
                        "timestamp": "2026-04-12T00:05:00Z",
                        "platform": "reddit",
                        "agent_id": 2,
                        "agent_name": "Bob",
                        "action_type": "CREATE_COMMENT",
                        "action_args": {"content": "Agreed."},
                        "success": True,
                    }
                ),
                json.dumps(
                    {
                        "round_num": 1,
                        "timestamp": "2026-04-12T00:10:00Z",
                        "platform": "twitter",
                        "agent_id": 1,
                        "agent_name": "Alice",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": "Need caregiver relief."},
                        "success": True,
                    }
                ),
                json.dumps(
                    {
                        "round_num": 1,
                        "timestamp": "2026-04-12T00:12:00Z",
                        "platform": "reddit",
                        "agent_id": 3,
                        "agent_name": "Cara",
                        "action_type": "CREATE_POST",
                        "action_args": {"content": ""},
                        "success": True,
                    }
                ),
            ]
        )
        + "\n",
    )

    manifest = store.update(run_id, status="completed")
    payload = build_completed_run_eval(manifest, store.run_dir(run_id))

    assert payload["metrics"]["configured_agent_count"] == 4
    assert payload["metrics"]["active_agent_coverage_ratio"] == 0.75
    assert payload["metrics"]["platform_coverage_ratio"] == 1.0
    assert payload["metrics"]["coverage_score"] == 0.81
    assert payload["metrics"]["local_diversity_score"] == 0.88
    assert payload["metrics"]["complexity_score"] == 0.61
    assert payload["metrics"]["critic_rejection_rate"] == 0.5
    assert "heuristic critic rejected a large share of simulated actions" in payload["risks"]


def test_runs_export_emits_run_eval_for_completed_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
):
    monkeypatch.setattr(Config, "UPLOAD_FOLDER", str(tmp_path / "uploads"))

    store = RunStore()
    manifest = store.create("Predict reaction", [], project_name="Eval Export")
    run_id = manifest["run_id"]
    store.write_json(run_id, "simulation/timeline.json", [{"round_num": 0, "total_actions": 4}])
    store.record_artifact(run_id, "timeline_json", "simulation/timeline.json")
    store.write_json(
        run_id,
        "simulation/top_agents.json",
        [{"agent_name": "Caregivers", "total_actions": 4}],
    )
    store.record_artifact(run_id, "top_agents", "simulation/top_agents.json")
    store.update(run_id, status="completed")

    exit_code = main(["runs", "export", run_id, "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert "run_eval" in payload["artifacts"]

    eval_payload = json.loads(Path(payload["artifacts"]["run_eval"]).read_text(encoding="utf-8"))
    assert eval_payload["artifact_type"] == "echo.run_eval.v1"
    assert eval_payload["metrics"]["total_actions"] == 4
