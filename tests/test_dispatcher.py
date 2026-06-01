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
    assert "brand" in payload["data"]["foundation"]
    assert payload["data"]["foundation"]["voice"]["primary_artifact"] == "voice_pack.v1"
    assert "studio-generation" in payload["data"]["extension_model"]["families"]
    assert payload["data"]["members"]["protocols"]["json_contract"] == (
        "library layer, not an operator CLI"
    )
    assert payload["data"]["members"]["voice"]["owns_artifact"] == "voice_pack.v1"
    assert payload["data"]["members"]["studio"]["runtime"] == "node"


def test_quickstart_full_operator_json_lists_python_and_node_steps() -> None:
    result = runner.invoke(cli.app, ["quickstart", "--profile", "full-operator", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["data"]["profile"] == "full-operator"
    assert payload["data"]["commands"] == [
        "uv sync --group dev",
        "make install-forecast-simulation",
        "cd studio && pnpm install",
    ]


def test_doctor_reports_member_probe_failures(monkeypatch) -> None:
    fake_bins = {
        "agentcy-voice": "/tmp/agentcy-voice",
        "agentcy-briefs": "/tmp/agentcy-briefs",
        "agentcy-forecast": "/tmp/agentcy-forecast",
        "agentcy-measure": "/tmp/agentcy-measure",
        "node": "/tmp/node",
    }

    def fake_which(name: str) -> str | None:
        return fake_bins.get(name)

    def fake_probe(command: list[str]) -> bool:
        joined = " ".join(command)
        return "agentcy-forecast" not in joined and " help " not in f" {joined} "

    monkeypatch.setattr(cli.shutil, "which", fake_which)
    monkeypatch.setattr(cli, "_studio_bin", lambda: "/tmp/agentcy-studio")
    monkeypatch.setattr(cli, "_probe_member", fake_probe)
    monkeypatch.setattr(cli, "_capture_optional_json", lambda command: None)

    result = runner.invoke(cli.app, ["doctor", "--json"])

    assert result.exit_code == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert payload["data"]["forecast"]["reachable"] is False
    assert payload["data"]["studio"]["reachable"] is False


def test_doctor_reports_ok_when_members_are_present_and_reachable(monkeypatch) -> None:
    fake_bins = {
        "agentcy-voice": "/tmp/agentcy-voice",
        "agentcy-briefs": "/tmp/agentcy-briefs",
        "agentcy-forecast": "/tmp/agentcy-forecast",
        "agentcy-measure": "/tmp/agentcy-measure",
        "node": "/tmp/node",
    }

    monkeypatch.setattr(cli.shutil, "which", lambda name: fake_bins.get(name))
    monkeypatch.setattr(cli, "_studio_bin", lambda: "/tmp/agentcy-studio")
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
    try:
        env = cli._subprocess_env()

        assert env["LLM_PROVIDER"] == "claude-cli"
        assert env["CLAUDE_MODEL"] == "haiku"
    finally:
        cli._OVERRIDES.provider = None
        cli._OVERRIDES.model = None


def test_member_json_normalizes_member_envelope_payload(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(command, capture_output, text, env):
        seen["command"] = command
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "status": "ok",
                    "command": "study",
                    "data": {"study_verdict": "aligned"},
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(cli, "_resolve_bin", lambda name: f"/tmp/{name}")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = runner.invoke(
        cli.app,
        ["member", "measure", "--json", "study", "--manifest", "demo.json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["command"] == "member"
    assert payload["data"]["member"] == "measure"
    assert payload["data"]["member_command"] == "study"
    assert payload["data"]["result"] == {"study_verdict": "aligned"}
    assert seen["command"] == [
        "/tmp/agentcy-measure",
        "--json",
        "study",
        "--manifest",
        "demo.json",
    ]


def test_member_json_normalizes_forecast_payload_and_injects_subcommand_json(monkeypatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(command, capture_output, text, env):
        seen["command"] = command
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"run_id": "run_demo", "status": "completed"}),
            stderr="",
        )

    monkeypatch.setattr(cli, "_resolve_bin", lambda name: f"/tmp/{name}")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = runner.invoke(cli.app, ["member", "forecast", "--json", "runs", "status", "run_demo"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["data"]["member"] == "forecast"
    assert payload["data"]["member_status"] == "ok"
    assert payload["data"]["result"] == {"run_id": "run_demo", "status": "completed"}
    assert seen["command"] == [
        "/tmp/agentcy-forecast",
        "runs",
        "status",
        "run_demo",
        "--json",
    ]



def test_pipeline_run_uses_explicit_pipeline_id_and_root_claude_provider_for_briefs(
    monkeypatch,
    tmp_path: Path,
) -> None:
    seen: dict[str, str | None] = {}

    def fake_member_json(bin_name: str, args: list[str]) -> dict:
        raise AssertionError((bin_name, args))

    def fake_studio_json(args: list[str]) -> dict:
        if args[:3] == ["run", "social.post", "--brand"]:
            return {
                "status": "ok",
                "command": "run",
                "data": {
                    "id": "run_studio_demo",
                    "workflow": "social.post",
                    "status": "in_review",
                    "currentStep": "review",
                },
            }
        if args[:2] == ["inspect", "run"]:
            return {"status": "ok", "command": "inspect", "data": {"artifacts": []}}
        raise AssertionError(args)

    def fake_run(command, capture_output, text, env, check=False, cwd=None):
        if "agentcy-briefs" in command[0]:
            seen["provider"] = env.get("AGENTCY_BRIEFS_LLM_PROVIDER")
            seen["model"] = env.get("CLAUDE_MODEL")
            seen["voice_arg"] = command[command.index("--voice-pack-id") + 1]
            seen["cwd"] = str(cwd)
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_text(
                json.dumps({"activation": {"channels": ["twitter"]}}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(cli, "_capture_member_json", fake_member_json)
    monkeypatch.setattr(cli, "_capture_studio_json", fake_studio_json)
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
            "--brand",
            "givecare",
            "--brief",
            "Before fall gets busy, make caregiving feel lighter",
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
    assert seen == {
        "provider": "claude-cli",
        "model": "sonnet",
        "voice_arg": "givecare.brand.core.voice.default",
        "cwd": str(Path(__file__).resolve().parents[1]),
    }



def test_pipeline_run_writes_manifest_with_discovered_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    seen: dict[str, str | None] = {}

    def fake_member_json(bin_name: str, args: list[str]) -> dict:
        raise AssertionError((bin_name, args))

    def fake_studio_json(args: list[str]) -> dict:
        if args[:3] == ["run", "social.post", "--brand"]:
            return {
                "status": "ok",
                "command": "run",
                "data": {
                    "id": "run_studio_demo",
                    "workflow": "social.post",
                    "status": "in_review",
                    "currentStep": "review",
                },
            }
        if args[:2] == ["inspect", "run"]:
            return {"status": "ok", "command": "inspect", "data": {"artifacts": []}}
        raise AssertionError(args)

    def fake_run(command, capture_output, text, env, check=False, cwd=None):
        if "agentcy-briefs" in command[0]:
            seen["provider"] = env.get("AGENTCY_BRIEFS_LLM_PROVIDER")
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_text(
                json.dumps({"activation": {"channels": ["twitter"]}}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(cli, "_capture_member_json", fake_member_json)
    monkeypatch.setattr(cli, "_capture_studio_json", fake_studio_json)
    monkeypatch.setattr(cli, "_resolve_bin", lambda name: f"/tmp/{name}")
    monkeypatch.setattr(cli.subprocess, "run", fake_run)

    result = runner.invoke(
        cli.app,
        [
            "pipeline",
            "run",
            "--brand",
            "givecare",
            "--brief",
            "Before fall gets busy, make caregiving feel lighter",
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
    assert manifest["artifacts"]["brief"].endswith("briefs/brief.v1.json")
    assert manifest["artifacts"]["studio_run"].endswith("studio/run.json")
    assert manifest["artifacts"]["studio_inspect"].endswith("studio/inspect.json")
    assert "voice_pack" not in manifest["artifacts"]
    assert "forecast" not in manifest["artifacts"]
    assert manifest["steps"]["voice_pack"]["status"] == "skipped"
    assert manifest["steps"]["forecast"]["status"] == "skipped"
    assert manifest["steps"]["studio"]["status"] == "ok"
    assert seen["provider"] == "mock"
    assert Path(payload["data"]["bundle"]).exists()
    assert Path(payload["data"]["report"]).exists()


def test_pipeline_run_can_record_persona_eval_and_optional_studio_branch(
    monkeypatch,
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "seed.md"
    source_file.write_text("seed", encoding="utf-8")

    def fake_member_json(bin_name: str, args: list[str]) -> dict:
        if bin_name == "agentcy-voice" and args[:2] == ["--json", "test"]:
            return {
                "persona": "scientist",
                "score": 0.83,
                "report_path": str(tmp_path / "persona_eval.json"),
            }
        if bin_name == "agentcy-voice" and args[:2] == ["--json", "export"]:
            return {"artifact_type": "voice_pack.v1", "voice_pack_id": "voice.demo"}
        if bin_name == "agentcy-forecast" and args[0] == "run":
            return {"run_id": "run_demo"}
        if bin_name == "agentcy-forecast" and args[:2] == ["runs", "export"]:
            return {
                "artifacts": {
                    "forecast_v1": str(tmp_path / "forecast.v1.json"),
                    "run_eval": str(
                        tmp_path / "forecast-runs" / "run_demo" / "eval" / "run_eval.v1.json"
                    ),
                }
            }
        raise AssertionError((bin_name, args))

    def fake_studio_json(args: list[str]) -> dict:
        if args[:3] == ["run", "social.post", "--brand"]:
            assert "--brief-file" in args
            return {
                "status": "ok",
                "command": "run",
                "data": {
                    "id": "run_studio_demo",
                    "workflow": "social.post",
                    "status": "in_review",
                    "currentStep": "review",
                },
            }
        if args[:2] == ["review", "approve"]:
            return {
                "status": "ok",
                "command": "review",
                "data": {"id": "run_studio_demo", "status": "approved"},
            }
        if args[0] == "publish":
            return {
                "status": "ok",
                "command": "publish",
                "data": {
                    "run": {"id": "run_studio_demo", "status": "approved"},
                    "runResult": {
                        "artifact_type": "run_result.v1",
                        "run_id": "run_studio_demo",
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
        if "agentcy-briefs" in command[0]:
            output_path = Path(command[command.index("--output") + 1])
            output_path.write_text(
                json.dumps({"activation": {"channels": ["twitter"]}}),
                encoding="utf-8",
            )
            return SimpleNamespace(returncode=0, stdout="", stderr="")
        raise AssertionError(command)

    monkeypatch.setattr(cli, "_capture_member_json", fake_member_json)
    monkeypatch.setattr(cli, "_capture_studio_json", fake_studio_json)
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
            "--with-forecast",
            "--studio-workflow",
            "social.post",
            "--publish",
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
    assert manifest["with_forecast"] is True
    assert manifest["publish"] is True
    assert manifest["studio_workflow"] == "social.post"
    assert manifest["artifacts"]["persona_eval"].endswith("voice/persona_eval.json")
    assert manifest["artifacts"]["voice_pack"].endswith("voice/voice_pack.v1.json")
    assert manifest["artifacts"]["forecast"].endswith("forecast.v1.json")
    assert manifest["artifacts"]["forecast_run_eval"].endswith("run_eval.v1.json")
    assert manifest["artifacts"]["studio_run_id"] == "run_studio_demo"
    assert manifest["artifacts"]["studio_run"].endswith("studio/run.json")
    assert manifest["artifacts"]["studio_review"].endswith("studio/review.json")
    assert manifest["artifacts"]["studio_publish"].endswith("studio/publish.json")
    assert manifest["artifacts"]["run_result"].endswith("studio/run_result.v1.json")
    assert manifest["artifacts"]["studio_inspect"].endswith("studio/inspect.json")
    assert manifest["artifacts"]["measure_preview"].endswith("measure/preview.json")
    assert manifest["steps"]["studio"]["data"]["workflow"] == "social.post"
    assert manifest["steps"]["measure"]["status"] == "skipped"


def test_pipeline_study_uses_manifest_artifacts(monkeypatch, tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "artifacts": {
                    "forecast": str(tmp_path / "forecast.json"),
                    "performance": str(tmp_path / "performance.json"),
                    "forecast_run_eval": str(tmp_path / "run_eval.json"),
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
                "run_id": "run_studio_demo",
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
                "run_id": "run_studio_demo",
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
    assert manifest["artifacts"]["studio_run_id"] == "run_studio_demo"
    assert manifest["steps"]["run_result"]["data"]["status"] == "published"
    assert manifest["steps"]["performance"]["data"]["performance_id"] == "perf.demo"



def test_local_studio_bin_resolves_repo_studio_bin() -> None:
    expected = Path(__file__).resolve().parents[1] / "studio" / "bin" / "studio.js"
    resolved = cli._studio_bin()

    assert resolved is not None
    assert Path(resolved) == expected
