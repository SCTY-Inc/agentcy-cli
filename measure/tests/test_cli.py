from __future__ import annotations

import json
from pathlib import Path

from agentcy_pulse.cli import main


def test_cli_writes_output_file(monkeypatch, tmp_path: Path) -> None:
    expected = {"artifact_type": "performance.v1", "performance_id": "test.performance"}

    def fake_adapt(sidecar_path: Path, *, run_result_path: Path) -> dict[str, str]:
        assert sidecar_path == Path("sidecar.json")
        assert run_result_path == Path("run-result.json")
        return expected

    monkeypatch.setattr("agentcy_pulse.cli.adapt_canonical_run_result_to_performance", fake_adapt)

    output_path = tmp_path / "performance.json"
    exit_code = main([
        "--sidecar",
        "sidecar.json",
        "--run-result",
        "run-result.json",
        "--output",
        str(output_path),
    ])

    assert exit_code == 0
    assert json.loads(output_path.read_text()) == expected


def test_cli_prints_json_when_output_is_omitted(monkeypatch, capsys) -> None:
    expected = {"artifact_type": "performance.v1", "performance_id": "stdout.performance"}

    monkeypatch.setattr(
        "agentcy_pulse.cli.adapt_canonical_run_result_to_performance",
        lambda sidecar_path, *, run_result_path: expected,
    )

    exit_code = main(["--sidecar", "sidecar.json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == expected


def test_cli_emits_standard_json_envelope_when_requested(monkeypatch, capsys) -> None:
    expected = {"artifact_type": "performance.v1", "performance_id": "json.performance"}

    monkeypatch.setattr(
        "agentcy_pulse.cli.adapt_canonical_run_result_to_performance",
        lambda sidecar_path, *, run_result_path: expected,
    )

    exit_code = main(["--sidecar", "sidecar.json", "--json"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "status": "ok",
        "command": "adapt",
        "data": expected,
    }
