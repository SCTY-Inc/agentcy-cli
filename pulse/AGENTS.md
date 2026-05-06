# AGENTS.md — agentcy-pulse

Pulse owns measurement, calibration, and study. It consumes `run_result.v1` and `forecast.v1`, then emits `performance.v1` and calibration reports.

## Current Surfaces

- Python distribution: `agentcy-pulse`
- Python import root: `agentcy_pulse`
- installed CLI: `agentcy-pulse`
- dispatcher alias: `agentcy pulse ...`
- writer contract: `performance.v1.writer = { repo: "cli-metrics", module: "agentcy-pulse" }`

## Commands

```bash
agentcy-pulse adapt --run-result run_result.v1.json --sidecar sidecar.json --output performance.v1.json --json
agentcy-pulse calibrate --forecast forecast.v1.json --performance performance.v1.json --json
agentcy-pulse study --manifest pipeline_manifest.json --json
agentcy-pulse doctor --json
uv run pytest pulse/tests
```

All JSON commands emit `{status, command, data}` envelopes.

## Layout

```text
pulse/
  src/agentcy_pulse/
    adapter.py
    cli.py
  lab/              study workflow absorbed from legacy agentcy-lab
  tests/
```

## Guardrails

- Exit `0` success, `1` user error, `2` runtime error.
- `adapt` is read-only on its inputs.
- Do not reintroduce a standalone `agentcy-lab` surface.
- Use `agentcy-pulse calibrate`; it replaces `agentcy-lab calibration`.
