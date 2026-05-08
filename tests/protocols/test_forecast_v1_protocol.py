from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS_DIR = ROOT / "src" / "agentcy" / "protocols"
EXAMPLES_DIR = PROTOCOLS_DIR / "examples"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_forecast_examples_validate_against_canonical_schema():
    schema = _load_json(PROTOCOLS_DIR / "schemas" / "forecast.v1.schema.json")
    validator = Draft202012Validator(schema)

    for name in [
        "forecast.v1.completed-minimal.json",
        "forecast.v1.completed-rich.json",
    ]:
        validator.validate(_load_json(EXAMPLES_DIR / name))


def test_forecast_examples_preserve_completed_scope_lineage_and_provenance_boundaries():
    lineage_rules = (PROTOCOLS_DIR / "lineage-rules.md").read_text()
    brief = _load_json(EXAMPLES_DIR / "brief.v1.rich.json")
    minimal = _load_json(EXAMPLES_DIR / "forecast.v1.completed-minimal.json")
    rich = _load_json(EXAMPLES_DIR / "forecast.v1.completed-rich.json")

    for payload in [minimal, rich]:
        assert payload["writer"] == {"repo": "cli-mirofish", "module": "agentcy-echo"}
        assert payload["status"] == "completed"
        assert payload["brief_id"] == brief["brief_id"]
        assert payload["brand_id"] == brief["brand_id"]
        assert payload["lineage"]["source_brief_id"] == brief["brief_id"]

    assert "completed forecasts only" in lineage_rules
    assert "forecast_id" in lineage_rules
    assert "project_id" in lineage_rules
    assert "simulation_id" in lineage_rules
    assert "deferred" in lineage_rules

    assert "source_voice_pack_id" not in minimal["lineage"]
    assert rich["lineage"]["source_voice_pack_id"] == brief["lineage"]["source_voice_pack_id"]
    assert rich["lineage"]["campaign_id"] == brief["lineage"]["campaign_id"]
    assert rich["lineage"]["signal_id"] == brief["lineage"]["signal_id"]

    assert rich["provenance"] == {
        "project_id": "givecare.project.fall-briefing.v1",
        "graph_id": "givecare.graph.social-forecast.v3",
        "simulation_id": "givecare.simulation.fall-checkin.2026-04-12t0518z",
        "report_id": "givecare.report.fall-checkin.2026-04-12",
    }
