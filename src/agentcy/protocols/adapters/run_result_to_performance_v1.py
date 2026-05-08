from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from agentcy.protocols.utils import load_json

_PKG = Path(__file__).resolve().parent.parent
RUN_RESULT_SCHEMA_PATH = _PKG / "schemas" / "run_result.v1.schema.json"
PERFORMANCE_SCHEMA_PATH = _PKG / "schemas" / "performance.v1.schema.json"
CANONICAL_RUN_RESULT_PATH = _PKG / "examples" / "run_result.v1.published.json"
RUN_RESULT_WRITER = {"repo": "cli-phantom", "module": "agentcy-loom"}
PERFORMANCE_WRITER = {"repo": "cli-metrics", "module": "agentcy-pulse"}
ALLOWED_METRIC_KEYS = {
    "impressions",
    "reach",
    "engagements",
    "reactions",
    "likes",
    "comments",
    "shares",
    "saves",
    "clicks",
    "video_views",
    "engagement_rate",
    "ctr",
}
RESERVED_SIDECAR_KEYS = {
    "run_id",
    "brief_id",
    "brand_id",
    "writer",
    "workflow",
    "lineage",
}


class AdapterValidationError(ValueError):
    pass


def _validator(path: Path) -> Draft202012Validator:
    return Draft202012Validator(load_json(path))


def _validate_run_result(run_result: dict[str, Any]) -> None:
    _validator(RUN_RESULT_SCHEMA_PATH).validate(run_result)

    if run_result.get("artifact_type") != "run_result.v1":
        raise AdapterValidationError("Upstream artifact_type must be run_result.v1")
    if run_result.get("schema_version") != "v1":
        raise AdapterValidationError("Upstream schema_version must be v1")
    if run_result.get("writer") != RUN_RESULT_WRITER:
        raise AdapterValidationError("Upstream writer must be cli-phantom / agentcy-loom")
    if run_result.get("workflow") != "social.post":
        raise AdapterValidationError("Adapter only supports social.post workflow")
    if run_result.get("status") != "published":
        raise AdapterValidationError("Adapter only supports published run_result.v1 inputs")

    delivery = run_result.get("delivery") or {}
    if delivery.get("dry_run") is True:
        raise AdapterValidationError("Adapter rejects dry_run upstream inputs")

    published_platforms = [
        item for item in delivery.get("platforms", []) if item.get("status") == "published"
    ]
    if not published_platforms:
        raise AdapterValidationError("Upstream input must include at least one published delivery platform")


def _validate_sidecar(sidecar: dict[str, Any]) -> None:
    for key in ["performance_id", "measured_at"]:
        value = sidecar.get(key)
        if value is None:
            raise AdapterValidationError(f"Sidecar missing required field: {key}")

    if "observations" not in sidecar:
        raise AdapterValidationError("Sidecar missing required field: observations")

    observations = sidecar["observations"]
    if not isinstance(observations, list) or not observations:
        raise AdapterValidationError("Sidecar observations must be a non-empty list")

    for forbidden in RESERVED_SIDECAR_KEYS:
        if forbidden in sidecar:
            raise AdapterValidationError(f"Sidecar may not override canonical field: {forbidden}")

    for observation in observations:
        if not isinstance(observation, dict):
            raise AdapterValidationError("Each sidecar observation must be an object")
        if not observation.get("platform"):
            raise AdapterValidationError("Each sidecar observation must include platform")
        if "metrics" not in observation:
            raise AdapterValidationError("Each sidecar observation must include metrics")
        metrics = observation["metrics"]
        if not isinstance(metrics, dict) or not metrics:
            raise AdapterValidationError("Each sidecar observation must include a non-empty metrics object")
        invalid_keys = sorted(set(metrics) - ALLOWED_METRIC_KEYS)
        if invalid_keys:
            raise AdapterValidationError(
                f"Observation for platform {observation['platform']} uses unsupported metric keys: {', '.join(invalid_keys)}"
            )
        if "post_id" in observation or "url" in observation:
            raise AdapterValidationError("Sidecar observations may not invent or override publish locators")


def adapt_run_result_to_performance(
    run_result: dict[str, Any],
    sidecar: dict[str, Any],
    *,
    include_published_at: bool = True,
    include_captured_at: bool = True,
) -> dict[str, Any]:
    _validate_run_result(run_result)
    _validate_sidecar(sidecar)

    published_platforms = {
        item["platform"]: item
        for item in run_result["delivery"]["platforms"]
        if item.get("status") == "published"
    }

    observations: list[dict[str, Any]] = []
    for sidecar_observation in sidecar["observations"]:
        platform = sidecar_observation["platform"]
        upstream = published_platforms.get(platform)
        if upstream is None:
            raise AdapterValidationError(
                f"Observation platform {platform} does not match a canonical published delivery platform"
            )
        if not upstream.get("post_id") and not upstream.get("url"):
            raise AdapterValidationError(
                f"Published platform {platform} is missing both post_id and url in canonical run_result.v1"
            )

        adapted = {
            "platform": platform,
            "metrics": dict(sidecar_observation["metrics"]),
        }
        if upstream.get("post_id"):
            adapted["post_id"] = upstream["post_id"]
        if upstream.get("url"):
            adapted["url"] = upstream["url"]
        if include_published_at:
            adapted["published_at"] = run_result["completed_at"]
        if include_captured_at:
            adapted["captured_at"] = sidecar["measured_at"]
        observations.append(adapted)

    performance = {
        "artifact_type": "performance.v1",
        "schema_version": "v1",
        "performance_id": sidecar["performance_id"],
        "run_id": run_result["run_id"],
        "brief_id": run_result["brief_id"],
        "brand_id": run_result["brand_id"],
        "writer": dict(PERFORMANCE_WRITER),
        "workflow": run_result["workflow"],
        "measured_at": sidecar["measured_at"],
        "observations": observations,
    }

    if run_result.get("lineage"):
        performance["lineage"] = dict(run_result["lineage"])
    if sidecar.get("window"):
        performance["window"] = sidecar["window"]
    if sidecar.get("summary", {}).get("notes"):
        performance["summary"] = {"notes": list(sidecar["summary"]["notes"])}

    _validator(PERFORMANCE_SCHEMA_PATH).validate(performance)
    return performance


def adapt_from_paths(
    sidecar_path: Path,
    run_result_path: Path = CANONICAL_RUN_RESULT_PATH,
) -> dict[str, Any]:
    return adapt_run_result_to_performance(load_json(run_result_path), load_json(sidecar_path))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Adapt canonical published run_result.v1 plus a deterministic sidecar into performance.v1; this remains the bounded family-owned pulse seam and minimum future cli-metrics birth-contract adapter surface"
    )
    parser.add_argument("sidecar", type=Path, help="Path to deterministic measurement sidecar JSON")
    parser.add_argument(
        "--run-result",
        type=Path,
        default=CANONICAL_RUN_RESULT_PATH,
        help="Path to canonical run_result.v1 JSON (defaults to parent canonical fixture)",
    )
    parser.add_argument("--output", type=Path, help="Optional output path for performance.v1 JSON")
    args = parser.parse_args()

    performance = adapt_from_paths(args.sidecar, args.run_result)
    payload = json.dumps(performance, indent=2) + "\n"

    if args.output:
        args.output.write_text(payload)
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
