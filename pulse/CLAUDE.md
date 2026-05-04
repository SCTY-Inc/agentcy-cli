# CLAUDE.md — agentcy-pulse

Measurement, calibration, and study. Consumes `run_result.v1` (from loom) and `forecast.v1` (from echo), emits `performance.v1` and calibration reports.

## Commands

```bash
agentcy-pulse adapt --run-result run_result.v1.json --sidecar sidecar.json \
  --output performance.v1.json --json          # run_result → performance.v1

agentcy-pulse calibrate --forecast forecast.v1.json \
  --performance performance.v1.json --json     # forecast vs actual

agentcy-pulse study --manifest pipeline_manifest.json --json   # full study pass

agentcy-pulse doctor --json                    # readiness check
```

All commands emit `{"status": "ok"|"error", "command": str, "data": {...}}` with `--json`.

## Pipeline position

```
loom run_result.v1  ──→  pulse adapt  ──→  performance.v1
echo forecast.v1    ──┘
                         performance.v1 + forecast.v1  ──→  pulse calibrate
```

`agentcy pipeline study --manifest ...` auto-discovers forecast/echo/persona sidecars and runs pulse study in one shot.

## Layout

```
pulse/
  src/agentcy_pulse/
    __init__.py
    adapter.py      adapt_canonical_run_result_to_performance()
    cli.py          Typer CLI (adapt, calibrate, study, doctor)
  lab/              Study workflow (absorbed from legacy agentcy-lab)
  tests/
```

## History

`pulse` absorbed `agentcy-lab` — `agentcy-pulse calibrate` replaces `agentcy-lab calibration`. The lab module is now a subpackage under pulse.

## Guardrails

- Exit 0 success, 1 user error, 2 runtime error
- `--json` required for machine-readable output in pipeline context
- Never modify run_result artifacts — adapt is read-only on its inputs
