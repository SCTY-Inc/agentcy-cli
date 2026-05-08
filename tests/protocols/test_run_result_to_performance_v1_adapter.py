from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from agentcy.protocols.adapters.run_result_to_performance_v1 import (
    PERFORMANCE_WRITER,
    AdapterValidationError,
    adapt_run_result_to_performance,
)

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS_DIR = ROOT / "src" / "agentcy" / "protocols"
EXAMPLES_DIR = PROTOCOLS_DIR / "examples"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


@pytest.fixture()
def canonical_run_result() -> dict:
    return _load_json(EXAMPLES_DIR / "run_result.v1.published.json")


@pytest.fixture()
def rich_sidecar() -> dict:
    return {
        "performance_id": "givecare.performance.social-fall-checkin.7d.2026-04-19",
        "measured_at": "2026-04-19T17:23:11Z",
        "window": "7d-post-publish",
        "observations": [
            {
                "platform": "linkedin",
                "metrics": {
                    "impressions": 12640,
                    "reach": 11210,
                    "engagements": 522,
                    "reactions": 341,
                    "likes": 341,
                    "comments": 29,
                    "shares": 18,
                    "saves": 41,
                    "clicks": 93,
                    "engagement_rate": 0.0413,
                    "ctr": 0.0074,
                },
            },
            {
                "platform": "instagram",
                "metrics": {
                    "impressions": 8940,
                    "reach": 7710,
                    "engagements": 408,
                    "likes": 287,
                    "comments": 22,
                    "shares": 34,
                    "saves": 65,
                    "engagement_rate": 0.0456,
                },
            },
        ],
        "summary": {
            "notes": [
                "Aggregate post-level metrics only.",
                "No audience-level export or user-level identifiers are included in canonical artifacts.",
            ]
        },
    }


@pytest.fixture()
def performance_validator() -> Draft202012Validator:
    return Draft202012Validator(_load_json(PROTOCOLS_DIR / "schemas" / "performance.v1.schema.json"))


def test_adapter_emits_schema_valid_performance_payload_from_canonical_published_fixture(
    canonical_run_result: dict,
    rich_sidecar: dict,
    performance_validator: Draft202012Validator,
):
    performance = adapt_run_result_to_performance(canonical_run_result, rich_sidecar)

    performance_validator.validate(performance)
    assert performance["writer"] == PERFORMANCE_WRITER
    assert performance["run_id"] == canonical_run_result["run_id"]
    assert performance["brief_id"] == canonical_run_result["brief_id"]
    assert performance["brand_id"] == canonical_run_result["brand_id"]
    assert performance["workflow"] == canonical_run_result["workflow"]
    assert performance["lineage"] == canonical_run_result["lineage"]
    assert performance["performance_id"] == rich_sidecar["performance_id"]
    assert performance["measured_at"] == rich_sidecar["measured_at"]
    assert performance["window"] == rich_sidecar["window"]
    assert performance["summary"] == rich_sidecar["summary"]

    upstream_platforms = {
        item["platform"]: item for item in canonical_run_result["delivery"]["platforms"]
    }
    for observation in performance["observations"]:
        upstream = upstream_platforms[observation["platform"]]
        assert observation["post_id"] == upstream["post_id"]
        assert observation["url"] == upstream["url"]
        assert observation["published_at"] == canonical_run_result["completed_at"]
        assert observation["captured_at"] == rich_sidecar["measured_at"]


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda payload: payload.update({"status": "dry_run"}), "published run_result.v1"),
        (lambda payload: payload.update({"workflow": "blog.post"}), "social.post workflow"),
        (
            lambda payload: payload["delivery"].update({"dry_run": True}),
            "rejects dry_run upstream inputs",
        ),
        (
            lambda payload: payload["delivery"].update({"platforms": []}),
            "at least one published delivery platform",
        ),
    ],
)
def test_adapter_rejects_invalid_upstream_run_results(canonical_run_result: dict, rich_sidecar: dict, mutator, message: str):
    run_result = copy.deepcopy(canonical_run_result)
    mutator(run_result)

    with pytest.raises(AdapterValidationError, match=message):
        adapt_run_result_to_performance(run_result, rich_sidecar)


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda payload: payload.pop("performance_id"), "performance_id"),
        (lambda payload: payload.pop("measured_at"), "measured_at"),
        (lambda payload: payload.update({"observations": []}), "non-empty list"),
        (
            lambda payload: payload["observations"].__setitem__(0, {"platform": "linkedin", "metrics": {}}),
            "non-empty metrics object",
        ),
        (
            lambda payload: payload["observations"].__setitem__(0, {"platform": "x", "metrics": {"impressions": 1}}),
            "does not match a canonical published delivery platform",
        ),
        (
            lambda payload: payload["observations"].__setitem__(0, {"platform": "linkedin", "metrics": {"followers": 1}}),
            "unsupported metric keys",
        ),
        (
            lambda payload: payload["observations"].__setitem__(0, {"platform": "linkedin", "post_id": "override", "metrics": {"impressions": 1}}),
            "invent or override publish locators",
        ),
        (lambda payload: payload.update({"run_id": "override"}), "override canonical field: run_id"),
    ],
)
def test_adapter_rejects_invalid_sidecars(canonical_run_result: dict, rich_sidecar: dict, mutator, message: str):
    sidecar = copy.deepcopy(rich_sidecar)
    mutator(sidecar)

    with pytest.raises(AdapterValidationError, match=message):
        adapt_run_result_to_performance(canonical_run_result, sidecar)


def test_adapter_rejects_missing_publish_locator_on_matched_platform(canonical_run_result: dict, rich_sidecar: dict):
    run_result = copy.deepcopy(canonical_run_result)
    run_result["delivery"]["platforms"][0].pop("post_id")
    run_result["delivery"]["platforms"][0].pop("url")

    with pytest.raises(AdapterValidationError, match="missing both post_id and url"):
        adapt_run_result_to_performance(run_result, rich_sidecar)
