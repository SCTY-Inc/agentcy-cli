from __future__ import annotations

import json
from pathlib import Path

from agentcy.brand.actions.write import WriteAction
from agentcy.brand.core.config import (
    BrandOpsConfig,
    config_resolution_candidates,
    get_env,
    load_config,
    resolve_config_path,
)
from agentcy.brand.core.decision import Decision, DecisionStatus, DecisionType
from agentcy.brand.core.storage import data_dir, default_data_dir, resolve_data_dir


def test_config_resolution_candidates_keep_current_compatibility_order(tmp_path, monkeypatch):
    home = tmp_path / "home"
    cwd = tmp_path / "workspace"
    home.mkdir()
    cwd.mkdir()

    monkeypatch.chdir(cwd)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)

    assert config_resolution_candidates() == [
        cwd / "brandos.yml",
        home / ".brandos" / "config.yml",
    ]


def test_load_config_prefers_brandops_config_env_over_default_candidates(tmp_path, monkeypatch):
    home = tmp_path / "home"
    cwd = tmp_path / "workspace"
    env_config = tmp_path / "env-config.yml"
    cwd_config = cwd / "brandos.yml"
    home_config = home / ".brandos" / "config.yml"

    cwd.mkdir()
    (home / ".brandos").mkdir(parents=True)
    cwd_config.write_text("default_provider: openai\n")
    home_config.write_text("default_provider: anthropic\n")
    env_config.write_text("default_provider: gemini\n")

    monkeypatch.chdir(cwd)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    monkeypatch.setenv("BRANDOPS_CONFIG", str(env_config))

    assert resolve_config_path() == env_config
    assert load_config().default_provider == "gemini"


def test_load_config_falls_back_from_repo_local_to_home_config(tmp_path, monkeypatch):
    home = tmp_path / "home"
    cwd = tmp_path / "workspace"
    cwd.mkdir()
    (home / ".brandos").mkdir(parents=True)

    repo_local = cwd / "brandos.yml"
    repo_local.write_text("default_provider: openai\n")
    home_config = home / ".brandos" / "config.yml"
    home_config.write_text("default_provider: anthropic\n")

    monkeypatch.chdir(cwd)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    monkeypatch.delenv("BRANDOPS_CONFIG", raising=False)

    assert resolve_config_path() == repo_local
    assert load_config().default_provider == "openai"

    repo_local.unlink()

    assert resolve_config_path() == home_config
    assert load_config().default_provider == "anthropic"


def test_load_config_defaults_preserve_brandos_vs_brand_os_split(tmp_path, monkeypatch):
    home = tmp_path / "home"
    cwd = tmp_path / "workspace"
    cwd.mkdir()
    home.mkdir()

    monkeypatch.chdir(cwd)
    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    monkeypatch.delenv("BRANDOPS_CONFIG", raising=False)

    config = load_config()

    assert isinstance(config, BrandOpsConfig)
    assert config.data_dir == home / ".brandos"
    assert resolve_config_path() is None


def test_get_env_uses_brandops_prefix(monkeypatch):
    monkeypatch.setenv("BRANDOPS_FROM_EMAIL", "ops@example.com")

    assert get_env("from_email") == "ops@example.com"
    assert get_env("missing", "fallback") == "fallback"


def test_data_dir_defaults_to_brand_os_path_but_respects_brandos_data_dir_override(tmp_path, monkeypatch):
    home = tmp_path / "home"
    override = tmp_path / "runtime-data"
    home.mkdir()

    monkeypatch.setattr("pathlib.Path.home", lambda: home)
    monkeypatch.delenv("BRANDOS_DATA_DIR", raising=False)

    assert default_data_dir() == home / ".brand-os"
    assert resolve_data_dir() == home / ".brand-os"
    assert data_dir() == home / ".brand-os"
    assert data_dir().exists()

    monkeypatch.setenv("BRANDOS_DATA_DIR", str(override))

    assert resolve_data_dir() == override
    assert data_dir() == override
    assert override.exists()


def test_write_action_defaults_to_storage_outputs_path(tmp_path):
    base_dir = tmp_path / "compat-runtime-root"
    decision = Decision(
        id="decision123",
        type=DecisionType.SIGNAL_ACTION,
        brand="acme",
        proposal={"action": "observe"},
        rationale="Keep an audit trail.",
        confidence=0.75,
        status=DecisionStatus.APPROVED,
    )

    result = WriteAction(base_dir=base_dir / "outputs").execute(
        decision,
        analysis={"summary": "Compatibility proof", "trends": []},
    )

    json_path = Path(result["json_path"])
    md_path = Path(result["md_path"])

    assert json_path.parent.parent == base_dir / "outputs" / "acme"
    assert md_path.parent == json_path.parent
    payload = json.loads(json_path.read_text())
    assert payload["decision"]["id"] == "decision123"
    assert "Compatibility proof" in md_path.read_text()
