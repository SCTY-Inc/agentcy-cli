from __future__ import annotations

import json
from pathlib import Path

import pytest

from agentcy_pulse import adapt_canonical_run_result_to_performance

ROOT = Path(__file__).resolve().parents[2]
SIDECAR_PATH = (
    ROOT
    / "protocols"
    / "tests"
    / "fixtures"
    / "run_result_to_performance_v1"
    / "sidecar.rich.json"
)
EXPECTED_PATH = (
    ROOT
    / "protocols"
    / "tests"
    / "fixtures"
    / "run_result_to_performance_v1"
    / "performance.rich.expected.json"
)

requires_family_workspace = pytest.mark.skipif(
    not SIDECAR_PATH.is_file() or not EXPECTED_PATH.is_file(),
    reason="canonical family protocols fixtures are not available in this checkout",
)


@requires_family_workspace
def test_cli_metrics_wrapper_matches_family_expected_fixture() -> None:
    performance = adapt_canonical_run_result_to_performance(SIDECAR_PATH)
    expected = json.loads(EXPECTED_PATH.read_text())
    assert performance == expected
