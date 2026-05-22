# agentcy-measure

Measurement and calibration member of the agentcy monorepo.

## Subcommands

```bash
agentcy-measure adapt      --sidecar <sidecar.json> [--run-result <run.json>] [--output <performance.json>] [--json]
agentcy-measure calibrate  --forecast <f.json> --performance <p.json> [--output <report.json>] [--json]
agentcy-measure study      [--forecast <f.json>] [--performance <p.json>] [--forecast-eval <run_eval.json>] [--persona-eval <persona_eval.json>] [--pipeline-manifest <manifest.json>] [--forecast-run-dir <run_dir>] [--output <report.json>] [--json]
agentcy-measure doctor                                                           # fixture check
```

Or via the dispatcher: `agentcy measure adapt ...`

## Install

```bash
uv sync  # from monorepo root
```

## Example

```bash
agentcy-measure adapt \
  --sidecar protocols/tests/fixtures/run_result_to_performance_v1/sidecar.rich.json \
  --output /tmp/performance.json \
  --json

agentcy-measure calibrate \
  --forecast protocols/examples/forecast.v1.completed-rich.json \
  --performance /tmp/performance.json \
  --json

agentcy-measure study \
  --forecast protocols/examples/forecast.v1.completed-rich.json \
  --performance protocols/examples/performance.v1.rich.json \
  --forecast-eval forecast/uploads/runs/<run_id>/eval/run_eval.v1.json \
  --persona-eval ~/.agentcy/evals/scientist/<timestamp>.json \
  --json

# Or resolve forecast / sidecars from a root pipeline manifest or forecast run dir
agentcy-measure study \
  --pipeline-manifest artifacts/pipelines/<pipeline_id>/manifest.json \
  --performance /tmp/performance.json \
  --json

# Or backfill the manifest once, then omit --performance on later study runs
agentcy pipeline update \
  --manifest artifacts/pipelines/<pipeline_id>/manifest.json \
  --run-result /tmp/run_result.json \
  --performance /tmp/performance.json \
  --json

agentcy-measure study \
  --pipeline-manifest artifacts/pipelines/<pipeline_id>/manifest.json \
  --json

agentcy-measure study \
  --forecast-run-dir forecast/uploads/runs/<run_id> \
  --performance /tmp/performance.json \
  --json
```

`study` is intentionally repo-local analysis: it keeps canonical `forecast.v1` / `performance.v1` narrow, then layers optional forecast/voice eval sidecars on top for operator review. Forecast run-eval sidecars now surface synthetic-signal metrics such as coverage, local diversity, complexity, and heuristic critic rejection rate, and `study` folds those into the guarded-risk verdict alongside the older round/top-agent checks. When `--pipeline-manifest` or `--forecast-run-dir` is provided, `study` auto-discovers the repo-local forecast and `run_eval` paths instead of making the operator wire them manually.

Legacy compatibility is still supported for `adapt`, so bare invocations like `agentcy-measure --sidecar sidecar.json` are treated as `agentcy-measure adapt --sidecar sidecar.json`.
