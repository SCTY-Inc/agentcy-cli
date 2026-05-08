from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS_DIR = ROOT / "src" / "agentcy" / "protocols"
EXAMPLES_DIR = PROTOCOLS_DIR / "examples"

FORBIDDEN_KEYS = {
    "token",
    "access_token",
    "refresh_token",
    "api_key",
    "secret",
    "password",
    "cookie",
    "session_id",
    "authorization",
    "auth",
    "email",
    "phone",
    "user_id",
    "audience",
    "followers",
    "viewers",
    "username",
    "handle",
}

FORBIDDEN_VALUE_SNIPPETS = {
    "bearer ",
    "api-key",
    "api_secret",
    "access-token",
    "refresh-token",
    "set-cookie",
    "session=",
    "@",
}


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def _iter_keys(payload):
    if isinstance(payload, dict):
        for key, value in payload.items():
            yield key
            yield from _iter_keys(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_keys(item)


def _iter_string_values(payload):
    if isinstance(payload, dict):
        for value in payload.values():
            yield from _iter_string_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _iter_string_values(item)
    elif isinstance(payload, str):
        yield payload


def test_performance_examples_validate_against_canonical_schema():
    schema = _load_json(PROTOCOLS_DIR / "schemas" / "performance.v1.schema.json")
    validator = Draft202012Validator(schema)

    for name in [
        "performance.v1.minimal.json",
        "performance.v1.rich.json",
    ]:
        validator.validate(_load_json(EXAMPLES_DIR / name))


def test_performance_examples_preserve_published_run_lineage_and_writer_ownership():
    lineage_rules = (PROTOCOLS_DIR / "lineage-rules.md").read_text()
    run_result = _load_json(EXAMPLES_DIR / "run_result.v1.published.json")
    minimal = _load_json(EXAMPLES_DIR / "performance.v1.minimal.json")
    rich = _load_json(EXAMPLES_DIR / "performance.v1.rich.json")

    for payload in [minimal, rich]:
        assert payload["writer"] == {"repo": "cli-metrics", "module": "agentcy-pulse"}
        assert payload["workflow"] == "social.post"
        assert payload["run_id"] == run_result["run_id"]
        assert payload["brief_id"] == run_result["brief_id"]
        assert payload["brand_id"] == run_result["brand_id"]
        assert payload["lineage"] == run_result["lineage"]
        assert payload["observations"]

        published_platforms = {
            item["platform"]: item
            for item in run_result["delivery"]["platforms"]
            if item["status"] == "published"
        }
        for observation in payload["observations"]:
            source = published_platforms[observation["platform"]]
            if "post_id" in observation:
                assert observation["post_id"] == source["post_id"]
            if "url" in observation:
                assert observation["url"] == source["url"]

    assert "performance.v1" in lineage_rules
    assert "published `social.post`" in lineage_rules
    assert "no tokens, secrets, auth material" in lineage_rules


def test_performance_examples_exclude_secrets_auth_and_user_level_pii_fields():
    for name in [
        "performance.v1.minimal.json",
        "performance.v1.rich.json",
    ]:
        payload = _load_json(EXAMPLES_DIR / name)
        seen_keys = {key.lower() for key in _iter_keys(payload)}
        assert seen_keys.isdisjoint(FORBIDDEN_KEYS), name

        string_values = [value.lower() for value in _iter_string_values(payload)]
        assert not any(snippet in value for value in string_values for snippet in FORBIDDEN_VALUE_SNIPPETS), name
        assert not any(value.startswith("mailto:") or value.startswith("tel:") for value in string_values), name
