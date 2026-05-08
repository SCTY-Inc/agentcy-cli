from __future__ import annotations

import json
from types import SimpleNamespace

import agentcy.brand.core.llm as llm


def test_get_provider_uses_llm_provider_env_when_brandops_provider_is_unset(monkeypatch) -> None:
    monkeypatch.delenv("BRANDOPS_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("LLM_PROVIDER", "claude-cli")
    monkeypatch.setattr(
        llm.shutil,
        "which",
        lambda name: "/tmp/claude" if name == "claude" else None,
    )

    provider = llm.get_provider()

    assert isinstance(provider, llm.ClaudeCLIProvider)



def test_claude_cli_provider_complete_json_uses_cli_output(monkeypatch) -> None:
    captured: dict[str, list[str]] = {}
    monkeypatch.setenv("CLAUDE_MODEL", "sonnet")
    monkeypatch.setattr(
        llm.shutil,
        "which",
        lambda name: "/tmp/claude" if name == "claude" else None,
    )

    def fake_run(command, capture_output, text, timeout, cwd):
        _ = capture_output
        captured["command"] = command
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"result": '{"insights": ["Care is infrastructure"]}'}),
            stderr="",
        )

    monkeypatch.setattr(llm.subprocess, "run", fake_run)

    provider = llm.ClaudeCLIProvider()
    result = provider.complete_json(
        prompt="Research GiveCare.",
        system="Return JSON.",
        default={"insights": []},
    )

    assert result == {"insights": ["Care is infrastructure"]}
    assert captured["command"][:2] == ["/tmp/claude", "-p"]
    assert "--model" in captured["command"]
    assert "sonnet" in captured["command"]
    assert "--output-format" in captured["command"]
