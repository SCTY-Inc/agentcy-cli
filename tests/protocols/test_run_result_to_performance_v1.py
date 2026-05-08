from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS_DIR = ROOT / "src" / "agentcy" / "protocols"
EXAMPLES_DIR = PROTOCOLS_DIR / "examples"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_published_run_result_example_is_a_valid_upstream_reference_for_performance_examples():
    run_result_schema = _load_json(PROTOCOLS_DIR / "schemas" / "run_result.v1.schema.json")
    performance_schema = _load_json(PROTOCOLS_DIR / "schemas" / "performance.v1.schema.json")

    run_validator = Draft202012Validator(run_result_schema)
    performance_validator = Draft202012Validator(performance_schema)

    run_result = _load_json(EXAMPLES_DIR / "run_result.v1.published.json")
    performance_examples = [
        _load_json(EXAMPLES_DIR / "performance.v1.minimal.json"),
        _load_json(EXAMPLES_DIR / "performance.v1.rich.json"),
    ]

    run_validator.validate(run_result)
    assert run_result["writer"] == {"repo": "cli-phantom", "module": "agentcy-loom"}
    assert run_result["status"] == "published"
    assert run_result["workflow"] == "social.post"

    published_platforms = {
        item["platform"]: item
        for item in run_result["delivery"]["platforms"]
        if item["status"] == "published"
    }
    assert published_platforms

    for payload in performance_examples:
        performance_validator.validate(payload)

        assert payload["writer"] == {"repo": "cli-metrics", "module": "agentcy-pulse"}
        assert payload["workflow"] == run_result["workflow"]
        assert payload["run_id"] == run_result["run_id"]
        assert payload["brief_id"] == run_result["brief_id"]
        assert payload["brand_id"] == run_result["brand_id"]
        assert payload["lineage"] == run_result["lineage"]

        observation_platforms = {item["platform"] for item in payload["observations"]}
        assert observation_platforms.issubset(published_platforms)

        for observation in payload["observations"]:
            source = published_platforms[observation["platform"]]
            assert "message" not in observation
            if "post_id" in observation:
                assert observation["post_id"] == source["post_id"]
            if "url" in observation:
                assert observation["url"] == source["url"]


def test_lineage_rules_lock_the_run_result_to_performance_slice_and_one_writer_per_artifact():
    lineage_rules = (PROTOCOLS_DIR / "lineage-rules.md").read_text()

    assert "performance.v1.run_id" in lineage_rules
    assert "performance.v1.brief_id" in lineage_rules
    assert '`performance.v1.writer` must remain `{ "repo": "cli-metrics", "module": "agentcy-pulse" }`' in lineage_rules
    assert '`run_result.v1.writer` must remain `{ "repo": "cli-phantom", "module": "agentcy-loom" }`' in lineage_rules
    assert "published `social.post` outcomes only" in lineage_rules
