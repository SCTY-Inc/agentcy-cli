from __future__ import annotations

import json

from typer.testing import CliRunner

from agentcy.brand.cli import app

runner = CliRunner()


def test_catalog_json_exposes_boundary_and_persona_deprecation() -> None:
    result = runner.invoke(app, ["--json", "catalog"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["artifact_owner"] == "brief.v1"
    assert payload["preferred_surfaces"] == ["brand", "signals", "intel", "plan"]
    assert payload["deprecated_surfaces"][0]["command_group"] == "persona"
    assert payload["deprecated_surfaces"][0]["replacement"] == "agentcy-vox"


def test_global_json_overrides_brand_list_table_default(monkeypatch) -> None:
    monkeypatch.setattr("agentcy.brand.core.brands.discover_brands", lambda: ["acme"])
    monkeypatch.setattr("agentcy.brand.core.brands.get_brand_dir", lambda name: f"/tmp/{name}")

    result = runner.invoke(app, ["--json", "brand", "list"])

    assert result.exit_code == 0
    assert json.loads(result.stdout) == ["acme"]


def test_global_json_overrides_publish_platforms_table_default(monkeypatch) -> None:
    monkeypatch.setattr("agentcy.brand.publish.platforms.list_platforms", lambda: ["twitter"])
    monkeypatch.setattr(
        "agentcy.brand.publish.rate_limit.get_rate_status",
        lambda: {"twitter": {"posts_last_hour": 1, "limit": 5}},
    )

    result = runner.invoke(app, ["--json", "publish", "platforms"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["available"] == ["twitter"]
    assert payload["rate_status"]["twitter"]["limit"] == 5


def test_global_json_overrides_plan_list_table_default(monkeypatch) -> None:
    monkeypatch.setattr(
        "agentcy.brand.plan.store.list_campaigns",
        lambda: [
            {
                "id": "campaign.demo",
                "brief": "Test pipeline brief",
                "brand": "acme",
                "stages": ["research", "strategy"],
                "created_at": "2026-04-22T00:00:00Z",
            }
        ],
    )

    result = runner.invoke(app, ["--json", "plan", "list"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload[0]["id"] == "campaign.demo"
    assert payload[0]["brand"] == "acme"


def test_json_envelope_wraps_brand_list(monkeypatch) -> None:
    monkeypatch.setattr("agentcy.brand.core.brands.discover_brands", lambda: ["acme"])
    monkeypatch.setattr("agentcy.brand.core.brands.get_brand_dir", lambda name: f"/tmp/{name}")

    result = runner.invoke(app, ["--json-envelope", "brand", "list"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload == {
        "status": "ok",
        "command": "brand.list",
        "data": ["acme"],
    }


def test_json_envelope_wraps_config_profiles(monkeypatch) -> None:
    monkeypatch.setattr(
        "agentcy.brand.core.config.get_config",
        lambda: type(
            "Config",
            (),
            {
                "brands_dir": "brands",
                "data_dir": ".brand_os",
                "default_provider": "gemini",
                "default_model": "gemini-2.5-pro",
            },
        )(),
    )

    result = runner.invoke(app, ["--json-envelope", "config", "profiles"])

    assert result.exit_code == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["command"] == "config.profiles"
    assert payload["data"]["default_provider"] == "gemini"
    assert payload["data"]["default_model"] == "gemini-2.5-pro"
