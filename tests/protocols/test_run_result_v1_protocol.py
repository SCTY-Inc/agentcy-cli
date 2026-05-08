from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS_DIR = ROOT / "src" / "agentcy" / "protocols"
EXAMPLES_DIR = PROTOCOLS_DIR / "examples"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_run_result_examples_validate_against_canonical_schema():
    schema = _load_json(PROTOCOLS_DIR / "schemas" / "run_result.v1.schema.json")
    validator = Draft202012Validator(schema)

    for name in [
        "run_result.v1.dry-run.json",
        "run_result.v1.published.json",
        "run_result.v1.failed.json",
    ]:
        validator.validate(_load_json(EXAMPLES_DIR / name))


def test_run_result_examples_preserve_brief_lineage_and_writer_ownership():
    lineage_rules = (PROTOCOLS_DIR / "lineage-rules.md").read_text()
    brief = _load_json(EXAMPLES_DIR / "brief.v1.rich.json")
    dry_run = _load_json(EXAMPLES_DIR / "run_result.v1.dry-run.json")
    published = _load_json(EXAMPLES_DIR / "run_result.v1.published.json")
    failed = _load_json(EXAMPLES_DIR / "run_result.v1.failed.json")

    for payload in [dry_run, published, failed]:
        assert payload["writer"] == {"repo": "cli-phantom", "module": "agentcy-loom"}
        assert payload["brief_id"] == brief["brief_id"]
        assert payload["brand_id"] == brief["brand_id"]
        assert payload["lineage"]["source_voice_pack_id"] == brief["lineage"]["source_voice_pack_id"]
        assert payload["lineage"]["campaign_id"] == brief["lineage"]["campaign_id"]
        assert payload["lineage"]["signal_id"] == brief["lineage"]["signal_id"]

    assert dry_run["status"] == "dry_run"
    assert dry_run["delivery"]["dry_run"] is True

    assert published["status"] == "published"
    assert all(item["status"] == "published" for item in published["delivery"]["platforms"])

    assert failed["status"] == "failed"
    assert failed["parent_run_id"] != failed["run_id"]
    assert failed["error"]["step"] == failed["current_step"]

    assert "run_result.v1" in lineage_rules
    assert "parent_run_id" in lineage_rules
    assert "dry_run" in lineage_rules
