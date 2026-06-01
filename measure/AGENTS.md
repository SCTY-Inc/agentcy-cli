# AGENTS.md — agentcy-measure

Measure owns measurement, calibration, and study. It consumes `run_result.v1` and `forecast.v1`, then emits `performance.v1` and calibration reports.

## Current Surfaces

- Python distribution: `agentcy-measure`
- Python import root: `agentcy_measure`
- installed CLI: `agentcy-measure`
- dispatcher alias: `agentcy measure ...`
- writer contract: `performance.v1.writer = { repo: "agentcy-measure", module: "agentcy-measure" }`

## Commands

```bash
agentcy-measure adapt --run-result run_result.v1.json --sidecar sidecar.json --output performance.v1.json --json
agentcy-measure calibrate --forecast forecast.v1.json --performance performance.v1.json --json
agentcy-measure study --manifest pipeline_manifest.json --json
agentcy-measure doctor --json
uv run pytest measure/tests
```

All JSON commands emit `{status, command, data}` envelopes.

## Layout

```text
measure/
  src/agentcy_measure/
    adapter.py
    calibration.py
    cli.py
  tests/
```

## Guardrails

- Exit `0` success, `1` user error, `2` runtime error.
- `adapt` is read-only on its inputs.
- Do not reintroduce a standalone `agentcy-lab` surface.
- Use `agentcy-measure calibrate`; it replaces `agentcy-lab calibration`.
