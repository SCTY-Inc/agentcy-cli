from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from agentcy.protocols.adapters.run_result_to_performance_v1 import (
    AdapterValidationError,
    adapt_from_paths,
    adapt_run_result_to_performance,
)
from tests.protocols.test_performance_v1_protocol import (
    FORBIDDEN_KEYS,
    FORBIDDEN_VALUE_SNIPPETS,
    _iter_keys,
    _iter_string_values,
)

ROOT = Path(__file__).resolve().parents[2]
_PKG = ROOT / "src" / "agentcy" / "protocols"
PROTOCOLS_DIR = _PKG
EXAMPLES_DIR = _PKG / "examples"
FIXTURES_DIR = ROOT / "tests" / "fixtures" / "run_result_to_performance_v1"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.fixture()
def canonical_run_result() -> dict:
    return _load_json(EXAMPLES_DIR / "run_result.v1.published.json")


@pytest.fixture()
def rich_sidecar() -> dict:
    return _load_json(FIXTURES_DIR / "sidecar.rich.json")


@pytest.fixture()
def expected_performance() -> dict:
    return _load_json(FIXTURES_DIR / "performance.rich.expected.json")


@pytest.fixture()
def performance_validator() -> Draft202012Validator:
    return Draft202012Validator(_load_json(PROTOCOLS_DIR / "schemas" / "performance.v1.schema.json"))


def test_adapter_matches_golden_output_from_canonical_family_fixture(
    canonical_run_result: dict,
    rich_sidecar: dict,
    expected_performance: dict,
    performance_validator: Draft202012Validator,
):
    performance = adapt_run_result_to_performance(canonical_run_result, rich_sidecar)

    performance_validator.validate(performance)
    assert performance == expected_performance
    assert performance["lineage"] == canonical_run_result["lineage"]

    published_platforms = {
        item["platform"]: item
        for item in canonical_run_result["delivery"]["platforms"]
        if item["status"] == "published"
    }
    for observation in performance["observations"]:
        upstream = published_platforms[observation["platform"]]
        assert observation["post_id"] == upstream["post_id"]
        assert observation["url"] == upstream["url"]
        assert observation["captured_at"] == rich_sidecar["measured_at"]


def test_adapter_can_load_directly_from_fixture_paths_without_network_access(
    expected_performance: dict,
    performance_validator: Draft202012Validator,
):
    performance = adapt_from_paths(FIXTURES_DIR / "sidecar.rich.json")

    performance_validator.validate(performance)
    assert performance == expected_performance


def test_adapter_output_stays_free_of_tokens_secrets_auth_and_user_level_pii(expected_performance: dict):
    seen_keys = {key.lower() for key in _iter_keys(expected_performance)}
    assert seen_keys.isdisjoint(FORBIDDEN_KEYS)

    string_values = [value.lower() for value in _iter_string_values(expected_performance)]
    assert not any(snippet in value for value in string_values for snippet in FORBIDDEN_VALUE_SNIPPETS)
    assert not any(value.startswith("mailto:") or value.startswith("tel:") for value in string_values)


@pytest.mark.parametrize(
    ("run_result_name", "mutator", "message"),
    [
        ("run_result.v1.failed.json", None, "published run_result.v1"),
        ("run_result.v1.published.json", lambda payload: payload.update({"workflow": "blog.post"}), "social.post workflow"),
        ("run_result.v1.published.json", lambda payload: payload["delivery"].update({"dry_run": True}), "rejects dry_run upstream inputs"),
        (
            "run_result.v1.published.json",
            lambda payload: payload["delivery"]["platforms"].__setitem__(0, {"platform": "linkedin", "status": "published"}),
            "missing both post_id and url",
        ),
    ],
)
def test_adapter_rejects_out_of_scope_or_locatorless_upstream_inputs(
    rich_sidecar: dict,
    run_result_name: str,
    mutator,
    message: str,
):
    run_result = _load_json(EXAMPLES_DIR / run_result_name)
    if mutator is not None:
        mutator(run_result)

    with pytest.raises(AdapterValidationError, match=message):
        adapt_run_result_to_performance(run_result, rich_sidecar)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (
            lambda payload: payload["observations"].__setitem__(0, {"platform": "tiktok", "metrics": {"impressions": 1}}),
            "does not match a canonical published delivery platform",
        ),
    ],
)
def test_adapter_rejects_unmatched_sidecar_platforms(
    canonical_run_result: dict,
    rich_sidecar: dict,
    mutator,
    message: str,
):
    sidecar = copy.deepcopy(rich_sidecar)
    mutator(sidecar)

    with pytest.raises(AdapterValidationError, match=message):
        adapt_run_result_to_performance(canonical_run_result, sidecar)
