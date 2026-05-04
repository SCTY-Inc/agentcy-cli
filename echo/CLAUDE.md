# CLAUDE.md

## What this is

MiroFish — CLI-only swarm intelligence prediction engine. Feed documents + requirement, get a simulated social media prediction with report and visual snapshots.

Fork of [666ghj/MiroFish](https://github.com/666ghj/MiroFish), fully translated to English.

## Commands

```bash
uv sync                                    # base CLI/help/import install
uv sync --extra simulation                 # full simulation runtime
agentcy echo run --files f.pdf --requirement "..." --json   # run full pipeline
agentcy echo run --files f.pdf --requirement "..." --smoke --json   # deterministic smoke-mode artifact path
agentcy echo runs list --json              # list runs
agentcy echo runs status <id> --json       # check status
agentcy echo runs export <id> --json       # export artifacts (includes repo-local run_eval; forecast_v1 for brief-based runs)
# or directly:
agentcy-echo run --files f.pdf --requirement "..." --json
uv run python -m pytest -x                 # tests
```

## Layout

```
app/
  cli.py              Entry point (console_scripts: agentcy-echo)
  config.py            Env + validation (.env loaded automatically)
  cli_display.py       Rich visual pipeline display
  run_artifacts.py     Immutable run storage (RunStore)
  run_eval.py          Repo-local completed-run evaluation sidecar
  smoke_mode.py        Deterministic smoke-mode timeline/report builder
  visual_snapshots.py  SVG generation (no browser needed)
  core/                WorkbenchSession, TaskManager, ResourceLoader
  tools/               Composable pipeline steps (ontology, graph, prepare, run, report)
  services/            Business logic (graph, simulation, report, and LLM services)
  resources/           Persistence adapters (projects, documents, graph, simulations, reports)
  models/              Data models
  utils/
    llm_client.py      CLI-only LLM client (claude-cli, codex-cli)
    logger.py          Structured logging
scripts/               OASIS simulation runner scripts (subprocess)
tests/                 pytest
uploads/               Runtime data (gitignored)
data/                  Graph JSON storage (gitignored)
```

## Architecture

CLI (`cli.py`) orchestrates via `WorkbenchSession` which composes tools:
1. `GenerateOntologyTool` — LLM entity/relationship extraction
2. `BuildGraphTool` — ontology → JSON graph
3. `PrepareSimulationTool` — agent profile generation
4. `RunSimulationTool` — OASIS subprocess (Twitter + Reddit)
5. `GenerateReportTool` — single-pass report generation (ReACT loop available but not default)

The simulation-config stage now normalizes taxonomy-driven `scenario_buckets` under `event_config`, then derives aligned `initial_posts` / `scheduled_events` so generation covers multiple reaction lanes instead of a single undifferentiated seed prompt.

Each run produces an immutable directory under `uploads/runs/<run_id>/` with manifest, frozen inputs, graph, simulation data, report, a repo-local `eval/run_eval.v1.json` sidecar, SVG visuals, and logs. The run-eval sidecar now includes synthetic-signal metrics for coverage, local diversity, complexity, and heuristic critic rejection rate in addition to the older run-shape summary.

## Config

`.env` file at repo root. Key vars:
- `LLM_PROVIDER` — `claude-cli` (default) or `codex-cli`
- `CLAUDE_MODEL` — optional Claude alias/full name forwarded to `claude -p --model ...`

## Gotchas
- Simulation runs OASIS in a subprocess via `scripts/`. The scripts add the project root to `sys.path` to import from `app.utils.oasis_llm`.
- `camel-oasis==0.2.5` and `camel-ai==0.2.78` stay pinned in the optional `simulation` extra — upgrading either can break the simulation pipeline. The wheel is now vendored at `vendor/camel_oasis-0.2.5-py3-none-any.whl` and referenced via `[tool.uv.sources]` to protect against upstream URL rot.
- `report_agent.py` split into three files: `report_types.py` (enums, dataclasses, prompts), `report_manager.py` (file I/O), `report_agent.py` (ReportAgent class only). `ReportAgent.generate_report_fast()` is the active path; `generate_report()` is legacy ReACT.
- CLI uses Typer (not argparse). `app` and `runs_app` are the Typer app objects; tests use `typer.testing.CliRunner` to invoke commands.
- `graph_tools.py` is now the public assembly point for split graph retrieval modules (`graph_models.py`, `graph_retrieval.py`, `graph_search_tools.py`, `graph_interview.py`); callers should keep importing `GraphToolsService` from `app.services.graph_tools`.
- CLI display (`cli_display.py`) uses `rich.Live` on stderr. Suppresses service-layer logs to WARNING during display. `--json` mode bypasses rich entirely.
- `--smoke` keeps ontology, graph build, and profile/config generation live but skips the long-running OASIS subprocess; use it for fast e2e artifact checks or Python 3.12 validation.
- CLI automation now starts the full simulation subprocess with `--no-wait`, so the operator happy path exits instead of lingering in command-waiting mode.
- The single-platform OASIS scripts now emit action logs under `twitter/actions.jsonl` or `reddit/actions.jsonl`, which restores downstream timeline/report assembly for full runs.
- CLI runs now set `AGENTCY_LLM_TELEMETRY_FILE` to a run-local `logs/llm_telemetry.jsonl`, so Claude/Codex call metadata can be inspected after the run.
- Never trash `uploads/runs/` — run artifacts are the product. Each run is immutable and self-contained.
