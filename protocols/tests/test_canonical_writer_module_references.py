from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS_DIR = ROOT / "protocols"
EXAMPLES_DIR = PROTOCOLS_DIR / "examples"

CANONICAL_WRITERS = {
    "voice_pack.v1": {"repo": "agentcy-voice", "module": "agentcy-voice"},
    "brief.v1": {"repo": "agentcy-briefs", "module": "agentcy-briefs"},
    "forecast.v1": {"repo": "agentcy-forecast", "module": "agentcy-forecast"},
    "run_result.v1": {"repo": "agentcy-studio", "module": "agentcy-studio"},
    "performance.v1": {"repo": "agentcy-measure", "module": "agentcy-measure"},
}

SCHEMA_FILES = {
    "voice_pack.v1": PROTOCOLS_DIR / "voice_pack.v1.schema.json",
    "brief.v1": PROTOCOLS_DIR / "brief.v1.schema.json",
    "forecast.v1": PROTOCOLS_DIR / "forecast.v1.schema.json",
    "run_result.v1": PROTOCOLS_DIR / "run_result.v1.schema.json",
    "performance.v1": PROTOCOLS_DIR / "performance.v1.schema.json",
}

EXAMPLE_FILES = {
    "voice_pack.v1": [
        EXAMPLES_DIR / "voice_pack.v1.minimal.json",
        EXAMPLES_DIR / "voice_pack.v1.rich.json",
    ],
    "brief.v1": [
        EXAMPLES_DIR / "brief.v1.minimal.json",
        EXAMPLES_DIR / "brief.v1.rich.json",
    ],
    "forecast.v1": [
        EXAMPLES_DIR / "forecast.v1.completed-minimal.json",
        EXAMPLES_DIR / "forecast.v1.completed-rich.json",
    ],
    "run_result.v1": [
        EXAMPLES_DIR / "run_result.v1.dry-run.json",
        EXAMPLES_DIR / "run_result.v1.published.json",
        EXAMPLES_DIR / "run_result.v1.failed.json",
    ],
    "performance.v1": [
        EXAMPLES_DIR / "performance.v1.minimal.json",
        EXAMPLES_DIR / "performance.v1.rich.json",
        PROTOCOLS_DIR / "tests" / "fixtures" / "run_result_to_performance_v1" / "performance.rich.expected.json",
    ],
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_canonical_schemas_and_examples_use_agentcy_writer_pairs():
    for artifact_type, expected_writer in CANONICAL_WRITERS.items():
        schema = _load_json(SCHEMA_FILES[artifact_type])
        writer_properties = schema["properties"]["writer"]["properties"]
        assert writer_properties["repo"]["const"] == expected_writer["repo"]
        assert writer_properties["module"]["const"] == expected_writer["module"]

        for path in EXAMPLE_FILES[artifact_type]:
            payload = _load_json(path)
            assert payload["artifact_type"] == artifact_type
            assert payload["writer"] == expected_writer, path.name


def test_lineage_rules_pin_canonical_writer_pairs():
    lineage_rules = (PROTOCOLS_DIR / "lineage-rules.md").read_text()
    for artifact_type, expected_writer in CANONICAL_WRITERS.items():
        assert expected_writer["repo"] in lineage_rules
        assert artifact_type in lineage_rules
