import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from agentcy.forecast.config import Config
from agentcy.forecast.utils.llm_client import LLMClient


def test_claude_cli_uses_configured_model(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_run(command, capture_output, text, timeout, cwd):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": "ok"}), stderr="")

    monkeypatch.setattr(Config, "CLAUDE_MODEL", "haiku")
    monkeypatch.setattr("subprocess.run", fake_run)

    client = LLMClient(provider="claude-cli")
    response = client.chat([{"role": "user", "content": "hello"}])

    assert response == "ok"
    assert captured["command"] == [
        "claude",
        "-p",
        "--model",
        "haiku",
        "--output-format",
        "json",
        "USER: hello",
    ]


def test_claude_cli_omits_model_flag_when_unset(monkeypatch: pytest.MonkeyPatch):
    captured: dict[str, object] = {}

    def fake_run(command, capture_output, text, timeout, cwd):
        captured["command"] = command
        return SimpleNamespace(returncode=0, stdout=json.dumps({"result": "ok"}), stderr="")

    monkeypatch.setattr(Config, "CLAUDE_MODEL", None)
    monkeypatch.setattr("subprocess.run", fake_run)

    client = LLMClient(provider="claude-cli")
    client.chat([{"role": "user", "content": "hello"}])

    assert captured["command"] == [
        "claude",
        "-p",
        "--output-format",
        "json",
        "USER: hello",
    ]


def test_claude_cli_appends_telemetry_when_configured(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    telemetry_path = tmp_path / "llm.jsonl"

    def fake_run(command, capture_output, text, timeout, cwd):
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps(
                {
                    "result": "ok",
                    "duration_ms": 12,
                    "total_cost_usd": 0.01,
                    "modelUsage": {"claude-haiku": {"inputTokens": 10}},
                }
            ),
            stderr="",
        )

    monkeypatch.setattr(Config, "CLAUDE_MODEL", "haiku")
    monkeypatch.setenv("AGENTCY_LLM_TELEMETRY_FILE", str(telemetry_path))
    monkeypatch.setattr("subprocess.run", fake_run)

    client = LLMClient(provider="claude-cli")
    client.chat([{"role": "user", "content": "hello"}])

    lines = telemetry_path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    payload = json.loads(lines[0])
    assert payload["provider"] == "claude-cli"
    assert payload["model"] == "haiku"
    assert payload["total_cost_usd"] == 0.01
