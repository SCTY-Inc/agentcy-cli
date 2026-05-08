from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS_DIR = ROOT / "src" / "agentcy" / "protocols"
EXAMPLES_DIR = PROTOCOLS_DIR / "examples"

CANONICAL_WRITERS = {
    "voice_pack.v1": {"repo": "cli-prsna", "module": "agentcy-vox"},
    "brief.v1": {"repo": "brand-os", "module": "agentcy-compass"},
    "forecast.v1": {"repo": "cli-mirofish", "module": "agentcy-echo"},
    "run_result.v1": {"repo": "cli-phantom", "module": "agentcy-loom"},
    "performance.v1": {"repo": "cli-metrics", "module": "agentcy-pulse"},
}

SCHEMA_FILES = {
    "voice_pack.v1": PROTOCOLS_DIR / "schemas" / "voice_pack.v1.schema.json",
    "brief.v1": PROTOCOLS_DIR / "schemas" / "brief.v1.schema.json",
    "forecast.v1": PROTOCOLS_DIR / "schemas" / "forecast.v1.schema.json",
    "run_result.v1": PROTOCOLS_DIR / "schemas" / "run_result.v1.schema.json",
    "performance.v1": PROTOCOLS_DIR / "schemas" / "performance.v1.schema.json",
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


def test_all_canonical_schemas_and_examples_keep_current_repo_and_future_module_pairs():
    for artifact_type, expected_writer in CANONICAL_WRITERS.items():
        schema = _load_json(SCHEMA_FILES[artifact_type])
        writer_properties = schema["properties"]["writer"]["properties"]
        assert writer_properties["repo"]["const"] == expected_writer["repo"]
        assert writer_properties["module"]["const"] == expected_writer["module"]

        for path in EXAMPLE_FILES[artifact_type]:
            payload = _load_json(path)
            assert payload["artifact_type"] == artifact_type
            assert payload["writer"] == expected_writer, path.name


def test_lineage_rules_lock_writer_pairs():
    lineage_rules = (PROTOCOLS_DIR / "lineage-rules.md").read_text()

    expected_pairs = [
        '`voice_pack.v1.writer` must be `{ "repo": "cli-prsna", "module": "agentcy-vox" }`',
        '`brief.v1.writer` must be `{ "repo": "brand-os", "module": "agentcy-compass" }`',
        '`run_result.v1.writer` must be `{ "repo": "cli-phantom", "module": "agentcy-loom" }`',
        '`performance.v1.writer` must be `{ "repo": "cli-metrics", "module": "agentcy-pulse" }`',
    ]
    for expected in expected_pairs:
        assert expected in lineage_rules
