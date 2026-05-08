from __future__ import annotations

import json
from pathlib import Path

from agentcy.metrics.cli import main
from agentcy.metrics.synthetic_analysis import build_study_report

ROOT = Path(__file__).resolve().parents[2]
PROTOCOLS = ROOT / "src" / "agentcy" / "protocols" / "examples"


def test_build_study_report_merges_optional_eval_sidecars(tmp_path: Path):
    echo_eval = tmp_path / "echo-eval.json"
    echo_eval.write_text(
        json.dumps(
            {
                "artifact_type": "echo.run_eval.v1",
                "summary": {"activity_pattern": "burst", "thesis": "Relief framing wins."},
                "metrics": {
                    "round_coverage_ratio": 0.4,
                    "peak_round_share": 0.8,
                    "top_agent_share": 0.75,
                    "coverage_score": 0.38,
                    "local_diversity_score": 0.32,
                    "complexity_score": 0.29,
                    "critic_rejection_rate": 0.27,
                },
                "risks": ["one agent dominated the simulated activity mix"],
            }
        ),
        encoding="utf-8",
    )
    persona_eval = tmp_path / "persona-eval.json"
    persona_eval.write_text(
        json.dumps(
            {
                "score": 0.76,
                "difficulty_scores": {"stress": 0.55},
                "boundary_pass_rate": 0.7,
                "failure_modes": ["drops boundary under pressure"],
            }
        ),
        encoding="utf-8",
    )

    report = build_study_report(
        PROTOCOLS / "forecast.v1.completed-rich.json",
        PROTOCOLS / "performance.v1.rich.json",
        echo_eval_path=echo_eval,
        persona_eval_path=persona_eval,
    )

    assert report["study_verdict"] == "guarded"
    assert "echo_run_eval" in report["synthetic_signals"]
    assert report["synthetic_signals"]["echo_run_eval"]["thesis"] == "Relief framing wins."
    assert report["synthetic_signals"]["echo_run_eval"]["coverage_score"] == 0.38
    assert report["synthetic_signals"]["echo_run_eval"]["local_diversity_score"] == 0.32
    assert report["synthetic_signals"]["echo_run_eval"]["complexity_score"] == 0.29
    assert report["synthetic_signals"]["echo_run_eval"]["critic_rejection_rate"] == 0.27
    assert "persona_eval" in report["synthetic_signals"]
    assert any("persona behavior degraded" in risk for risk in report["risks"])
    assert any("synthetic coverage stayed narrow" in risk for risk in report["risks"])
    assert any("critic rejected too many simulated actions" in risk for risk in report["risks"])


def test_build_study_report_resolves_paths_from_pipeline_manifest(tmp_path: Path):
    forecast = PROTOCOLS / "forecast.v1.completed-rich.json"
    performance = PROTOCOLS / "performance.v1.rich.json"
    echo_eval = tmp_path / "echo-eval.json"
    echo_eval.write_text(
        json.dumps(
            {
                "artifact_type": "echo.run_eval.v1",
                "summary": {"activity_pattern": "burst"},
                "metrics": {
                    "round_coverage_ratio": 0.4,
                    "peak_round_share": 0.8,
                    "top_agent_share": 0.75,
                    "coverage_score": 0.38,
                    "local_diversity_score": 0.32,
                    "complexity_score": 0.29,
                    "critic_rejection_rate": 0.27,
                },
            }
        ),
        encoding="utf-8",
    )
    manifest = tmp_path / "pipeline.json"
    manifest.write_text(
        json.dumps(
            {
                "artifacts": {
                    "forecast": str(forecast),
                    "performance": str(performance),
                    "echo_run_eval": str(echo_eval),
                }
            }
        ),
        encoding="utf-8",
    )

    report = build_study_report(None, None, pipeline_manifest_path=manifest)

    assert report["forecast_id"] == "givecare.forecast.fall-checkin.completed-rich.2026-04-12"
    assert report["synthetic_signals"]["echo_run_eval"]["activity_pattern"] == "burst"



def test_cli_study_emits_standard_json_envelope(tmp_path: Path, capsys) -> None:
    echo_eval = tmp_path / "echo-eval.json"
    echo_eval.write_text(
        json.dumps(
            {
                "artifact_type": "echo.run_eval.v1",
                "summary": {"activity_pattern": "sustained"},
                "metrics": {
                    "round_coverage_ratio": 0.75,
                    "peak_round_share": 0.3,
                    "top_agent_share": 0.4,
                    "coverage_score": 0.82,
                    "local_diversity_score": 0.71,
                    "complexity_score": 0.58,
                    "critic_rejection_rate": 0.04,
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main(
        [
            "study",
            "--forecast",
            str(PROTOCOLS / "forecast.v1.completed-rich.json"),
            "--performance",
            str(PROTOCOLS / "performance.v1.rich.json"),
            "--echo-eval",
            str(echo_eval),
            "--json",
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ok"
    assert payload["command"] == "study"
    assert (
        payload["data"]["forecast_id"]
        == "givecare.forecast.fall-checkin.completed-rich.2026-04-12"
    )
