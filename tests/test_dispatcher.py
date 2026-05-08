from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from typer.testing import CliRunner

import agentcy.cli as cli
from agentcy import __version__

runner = CliRunner()


def test_version_command_uses_package_version() -> None:
    result = runner.invoke(cli.app, ["version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == f"agentcy {__version__}"


def test_catalog_json_describes_stage_owned_suite() -> None:
    result = runner.invoke(cli.app, ["catalog", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["command"] == "catalog"
    assert payload["data"]["suite"]["drop_in_package"] is False
    assert payload["data"]["members"]["protocols"]["json_contract"] == (
        "library layer, not an operator CLI"
    )
    assert payload["data"]["members"]["vox"]["owns_artifact"] == "voice_pack.v1"
    assert payload["data"]["members"]["loom"]["runtime"] == "node"


def test_quickstart_full_operator_json_lists_python_and_node_steps() -> None:
    result = runner.invoke(cli.app, ["quickstart", "--profile", "full-operator", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["data"]["profile"] == "full-operator"
    assert payload["data"]["commands"] == [
        "uv sync --group dev",
        "uv sync --extra simulation",
        "cd loom/runtime && pnpm install",
    ]


def test_doctor_reports_member_probe_failures(monkeypatch) -> None:
    fake_bins = {
        "agentcy persona": "/tmp/agentcy persona",
        "agentcy brand": "/tmp/agentcy brand",
        "agentcy forecast": "/tmp/agentcy forecast",
        "agentcy metrics": "/tmp/agentcy metrics",
        "node": "/tmp/node",
    }

    def fake_which(name: str) -> str | None:
        return fake_bins.get(name)

    def fake_probe(command: list[str]) -> bool:
        joined = " ".join(command)
        return "agentcy forecast" not in joined and " help " not in f" {joined} "

    monkeypatch.setattr(cli.shutil, "which", fake_which)
    monkeypatch.setattr(cli, "_loom_bin", lambda: "/tmp/agentcy studio")
    monkeypatch.setattr(cli, "_probe_member", fake_probe)
    monkeypatch.setattr(cli, "_capture_optional_json", lambda command: None)

    result = runner.invoke(cli.app, ["doctor", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert payload["data"]["echo"]["reachable"] is False
    assert payload["data"]["loom"]["reachable"] is False


def test_doctor_reports_ok_when_members_are_present_and_reachable(monkeypatch) -> None:
    fake_bins = {
        "agentcy persona": "/tmp/agentcy persona",
        "agentcy brand": "/tmp/agentcy brand",
        "agentcy forecast": "/tmp/agentcy forecast",
        "agentcy metrics": "/tmp/agentcy metrics",
        "node": "/tmp/node",
    }

    monkeypatch.setattr(cli.shutil, "which", lambda name: fake_bins.get(name))
    monkeypatch.setattr(cli, "_loom_bin", lambda: "/tmp/agentcy studio")
    monkeypatch.setattr(cli, "_probe_member", lambda command: True)
    monkeypatch.setattr(cli, "_capture_optional_json", lambda command: {"status": "ok"})

    result = runner.invoke(cli.app, ["doctor", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert all(
        info["reachable"]
        for name, info in payload["data"].items()
        if not name.startswith("_")
    )
    assert payload["data"]["_env"]["claude"] in {True, False}


def test_subprocess_env_includes_global_overrides() -> None:
    cli._OVERRIDES.provider = "claude-cli"
    cli._OVERRIDES.model = "haiku"

    env = cli._subprocess_env()

    assert env["LLM_PROVIDER"] == "claude-cli"
    assert env["CLAUDE_MODEL"] == "haiku"


def test_pipeline_run_uses_explicit_pipeline_id_and_root_claude_provider_for_compass(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")
    seen: dict[str, str | None] = {}

    def fake_member_json(bin_name: str, args: list[str]) -> dict:
        if bin_name == "agentcy persona" and args[:2] == ["--json", "export"]:
            return {"artifact_type": "voice_pack.v1", "voice_pack_id": "voice.demo"}
        if bin_name == "agentcy forecast" and args[0] == "run":
            return {"run_id": "run_demo"}
        if bin_name == "agentcy forecast" and args[:2] == ["runs", "export"]:
            return {
                "artifacts": {
                    "forecast_v1": str(tmp_path / "forecast.v1.json"),
                    "run_eval": str(
                        tmp_path / "echo-runs" / "run_demo" / "eval" / "run_eval.v1.json"
                    ),
                }
            }
        raise AssertionError((bin_name, args))

    def fake_run(command, capture_output, text, env, check=False, cwd=None):
        if "agentcy brand" in command[0]:
            seen["provider"] = env.get("BRANDOPS_LLM_PROVIDER")
            seen["model"] = env.get("CLAUDE_MODEL")
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_text(
                json.dumps({"activation": {"channels": ["twitter"]}}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(cli, "_capture_member_json", fake_member_json)
    monkeypatch.setattr(cli, "_resolve_bin", lambda name: f"/tmp/{name}")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = runner.invoke(
        cli.app,
        [
            "--provider",
            "claude-cli",
            "--model",
            "sonnet",
            "pipeline",
            "run",
            "--pipeline-id",
            "givecare-launch-01",
            "--persona",
            "scientist",
            "--brand",
            "givecare",
            "--brief",
            "Before fall gets busy, make caregiving feel lighter",
            "--files",
            str(source_file),
            "--smoke",
            "--output-dir",
            str(tmp_path / "pipelines"),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert Path(payload["data"]["manifest"]) == (
        tmp_path / "pipelines" / "givecare-launch-01" / "manifest.json"
    )
    assert seen == {"provider": "claude-cli", "model": "sonnet"}



def test_pipeline_run_writes_manifest_with_discovered_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")

    def fake_member_json(bin_name: str, args: list[str]) -> dict:
        if bin_name == "agentcy persona" and args[:2] == ["--json", "export"]:
            return {"artifact_type": "voice_pack.v1", "voice_pack_id": "voice.demo"}
        if bin_name == "agentcy forecast" and args[0] == "run":
            return {"run_id": "run_demo"}
        if bin_name == "agentcy forecast" and args[:2] == ["runs", "export"]:
            return {
                "artifacts": {
                    "forecast_v1": str(tmp_path / "forecast.v1.json"),
                    "run_eval": str(
                        tmp_path / "echo-runs" / "run_demo" / "eval" / "run_eval.v1.json"
                    ),
                }
            }
        raise AssertionError((bin_name, args))

    def fake_run(command, capture_output, text, env, check=False, cwd=None):
        if "agentcy brand" in command[0]:
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_text(
                json.dumps({"activation": {"channels": ["twitter"]}}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(cli, "_capture_member_json", fake_member_json)
    monkeypatch.setattr(cli, "_resolve_bin", lambda name: f"/tmp/{name}")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = runner.invoke(
        cli.app,
        [
            "pipeline",
            "run",
            "--persona",
            "scientist",
            "--brand",
            "givecare",
            "--brief",
            "Before fall gets busy, make caregiving feel lighter",
            "--files",
            str(source_file),
            "--smoke",
            "--output-dir",
            str(tmp_path / "pipelines"),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    manifest_path = Path(payload["data"]["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["brand_id"] == "givecare.brand.core"
    assert manifest["mode"] == "preview"
    assert manifest["artifacts"]["voice_pack"].endswith("vox/voice_pack.v1.json")
    assert manifest["artifacts"]["brief"].endswith("compass/brief.v1.json")
    assert manifest["artifacts"]["forecast"].endswith("forecast.v1.json")
    assert manifest["artifacts"]["echo_run_eval"].endswith("run_eval.v1.json")
    assert Path(payload["data"]["bundle"]).exists()
    assert Path(payload["data"]["report"]).exists()


def test_pipeline_run_can_record_persona_eval_and_optional_loom_branch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")

    def fake_member_json(bin_name: str, args: list[str]) -> dict:
        if bin_name == "agentcy persona" and args[:2] == ["--json", "test"]:
            return {
                "persona": "scientist",
                "score": 0.83,
                "report_path": str(tmp_path / "persona_eval.json"),
            }
        if bin_name == "agentcy persona" and args[:2] == ["--json", "export"]:
            return {"artifact_type": "voice_pack.v1", "voice_pack_id": "voice.demo"}
        if bin_name == "agentcy forecast" and args[0] == "run":
            return {"run_id": "run_demo"}
        if bin_name == "agentcy forecast" and args[:2] == ["runs", "export"]:
            return {
                "artifacts": {
                    "forecast_v1": str(tmp_path / "forecast.v1.json"),
                    "run_eval": str(
                        tmp_path / "echo-runs" / "run_demo" / "eval" / "run_eval.v1.json"
                    ),
                }
            }
        raise AssertionError((bin_name, args))

    def fake_loom_json(args: list[str]) -> dict:
        if args[:3] == ["run", "social.post", "--brand"]:
            assert "--brief-file" in args
            return {
                "status": "ok",
                "command": "run",
                "data": {
                    "id": "run_loom_demo",
                    "workflow": "social.post",
                    "status": "in_review",
                    "currentStep": "review",
                },
            }
        if args[:2] == ["review", "approve"]:
            return {
                "status": "ok",
                "command": "review",
                "data": {"id": "run_loom_demo", "status": "approved"},
            }
        if args[0] == "publish":
            return {
                "status": "ok",
                "command": "publish",
                "data": {
                    "run": {"id": "run_loom_demo", "status": "approved"},
                    "runResult": {
                        "artifact_type": "run_result.v1",
                        "run_id": "run_loom_demo",
                        "workflow": "social.post",
                        "status": "dry_run",
                    },
                },
            }
        if args[:2] == ["inspect", "run"]:
            return {
                "status": "ok",
                "command": "inspect",
                "data": {
                    "artifacts": [
                        {
                            "type": "draft_set",
                            "data": {
                                "variants": [
                                    {
                                        "id": "social-main",
                                        "hook": "Hook",
                                        "body": "Body",
                                        "cta": "CTA",
                                    }
                                ]
                            },
                        }
                    ]
                },
            }
        raise AssertionError(args)

    def fake_run(command, capture_output, text, env, check=False, cwd=None):
        if "agentcy brand" in command[0]:
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_text(
                json.dumps({"activation": {"channels": ["twitter"]}}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(cli, "_capture_member_json", fake_member_json)
    monkeypatch.setattr(cli, "_capture_loom_json", fake_loom_json)
    monkeypatch.setattr(cli, "_resolve_bin", lambda name: f"/tmp/{name}")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = runner.invoke(
        cli.app,
        [
            "pipeline",
            "run",
            "--persona",
            "scientist",
            "--persona-eval",
            "--brand",
            "givecare",
            "--brief",
            "Before fall gets busy, make caregiving feel lighter",
            "--files",
            str(source_file),
            "--loom-workflow",
            "social.post",
            "--smoke",
            "--output-dir",
            str(tmp_path / "pipelines"),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    manifest_path = Path(payload["data"]["manifest"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["persona_eval"] is True
    assert manifest["loom_workflow"] == "social.post"
    assert manifest["artifacts"]["persona_eval"].endswith("vox/persona_eval.json")
    assert manifest["artifacts"]["loom_run_id"] == "run_loom_demo"
    assert manifest["artifacts"]["loom_run"].endswith("loom/run.json")
    assert manifest["artifacts"]["loom_review"].endswith("loom/review.json")
    assert manifest["artifacts"]["loom_publish"].endswith("loom/publish.json")
    assert manifest["artifacts"]["run_result"].endswith("loom/run_result.v1.json")
    assert manifest["artifacts"]["loom_inspect"].endswith("loom/inspect.json")
    assert manifest["artifacts"]["pulse_preview"].endswith("pulse/preview.json")
    assert manifest["steps"]["loom"]["data"]["workflow"] == "social.post"
    assert manifest["steps"]["pulse"]["status"] == "skipped"


def test_pipeline_study_uses_manifest_artifacts(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "artifacts": {
                    "forecast": str(tmp_path / "forecast.json"),
                    "performance": str(tmp_path / "performance.json"),
                    "echo_run_eval": str(tmp_path / "run_eval.json"),
                    "persona_eval": str(tmp_path / "persona_eval.json"),
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        cli,
        "_capture_member_json",
        lambda bin_name, args: {
            "status": "ok",
            "command": "study",
            "data": {"study_verdict": "guarded", "recommendation": "inspect risks"},
        },
    )

    result = runner.invoke(
        cli.app,
        ["pipeline", "study", "--manifest", str(manifest_path), "--json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["data"]["report"]["study_verdict"] == "guarded"
    assert Path(payload["data"]["study"]).exists()



def test_pipeline_update_backfills_run_result_and_performance(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps({"artifacts": {}, "steps": {}}), encoding="utf-8")

    run_result_path = tmp_path / "run_result.v1.json"
    run_result_path.write_text(
        json.dumps(
            {
                "artifact_type": "run_result.v1",
                "run_id": "run_loom_demo",
                "workflow": "social.post",
                "status": "published",
            }
        ),
        encoding="utf-8",
    )
    performance_path = tmp_path / "performance.v1.json"
    performance_path.write_text(
        json.dumps(
            {
                "artifact_type": "performance.v1",
                "performance_id": "perf.demo",
                "run_id": "run_loom_demo",
                "measured_at": "2026-04-18T23:30:00Z",
            }
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        cli.app,
        [
            "pipeline",
            "update",
            "--manifest",
            str(manifest_path),
            "--run-result",
            str(run_result_path),
            "--performance",
            str(performance_path),
            "--json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    manifest = json.loads(Path(payload["data"]["manifest"]).read_text(encoding="utf-8"))
    assert manifest["artifacts"]["run_result"].endswith("run_result.v1.json")
    assert manifest["artifacts"]["performance"].endswith("performance.v1.json")
    assert manifest["artifacts"]["loom_run_id"] == "run_loom_demo"
    assert manifest["steps"]["run_result"]["data"]["status"] == "published"
    assert manifest["steps"]["performance"]["data"]["performance_id"] == "perf.demo"



def test_local_loom_bin_resolves_repo_runtime_bin() -> None:
    expected = Path(__file__).resolve().parents[1] / "src" / "studio" / "runtime" / "bin" / "loom.js"
    resolved = cli._loom_bin()

    assert resolved is not None
    assert Path(resolved) == expected
