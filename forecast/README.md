# agentcy-forecast

Part of the agentcy monorepo — invoke via `agentcy forecast` or `agentcy-forecast`.

A swarm intelligence prediction engine. Feed it documents describing any scenario, and agentcy-forecast simulates thousands of AI agents reacting on social media to predict how events will unfold.

> Fork of [666ghj/MiroFish](https://github.com/666ghj/MiroFish) — fully translated to English, CLI-only, Claude/Codex CLI support added.

## What it does

1. **Feed reality seeds** — PDFs, markdown, or text files (news articles, policy drafts, financial reports, anything)
2. **Describe what to predict** — natural language requirement
3. **agentcy-forecast builds a world** — extracts entities and relationships into a knowledge graph, generates AI agent personas with distinct personalities
4. **Agents simulate social media** — dual-platform simulation (Twitter + Reddit) where agents post, reply, like, argue, and follow each other
5. **Get a prediction report** — AI analyzes all simulation data and produces structured findings

## Quick start

### Prerequisites

- Python 3.11-3.12 for the base CLI package
- Python 3.11 for the optional simulation runtime (upstream `camel-oasis` does not support 3.12)
- `--smoke` works on the base CLI package and skips the Python-3.11-only OASIS runtime
- [uv](https://docs.astral.sh/uv/) (Python package manager)

### Setup

```bash
cp .env.example .env
# Base install: CLI/help/import surfaces
uv sync

# Full simulation runtime (recommended for actual runs, Python 3.11 only)
make install-forecast-simulation

# Readiness check for the full simulation runtime
forecast/.venv-simulation/bin/agentcy-forecast doctor --json
```

Base package installs intentionally keep the upstream OASIS/CAMEL simulation runtime out of the default workspace so `agentcy forecast --help`, smoke runs, and `import agentcy_forecast` can be proven independently of the pinned upstream dependency boundary. Full simulation uses `forecast/.venv-simulation`, created by `make install-forecast-simulation`, because that upstream stack still only supports Python 3.11.

### Run a simulation

```bash
# Full simulation after `make install-forecast-simulation`
forecast/.venv-simulation/bin/agentcy-forecast run \
  --files docs/policy.pdf notes/context.md \
  --requirement "Predict public reaction over 30 days" \
  --json

# Faster artifact proof path: skip the live OASIS runtime, keep the rest of the CLI flow
agentcy forecast run \
  --files docs/policy.pdf notes/context.md \
  --requirement "Predict public reaction over 30 days" \
  --smoke \
  --json

# List prior runs
agentcy forecast runs list --json

# Check run status
agentcy forecast runs status <run_id> --json

# Export artifacts (includes repo-local run_eval + canonical forecast_v1 for completed runs)
agentcy forecast runs export <run_id> --json

# Export just the repo-local run-shape eval sidecar
agentcy forecast runs export <run_id> --artifact run_eval --json

# Export just the canonical forecast file
agentcy forecast runs export <run_id> --artifact forecast_v1 --json
```

### CLI options

```
agentcy forecast run
  --files FILE [FILE ...]     Source documents (PDF, markdown, text)
  --requirement TEXT          What to predict
  --platform parallel|twitter|reddit   Simulation platform (default: parallel)
  --max-rounds N              Max simulation rounds (default: 10)
  --smoke                     Skip the live OASIS subprocess and emit deterministic smoke-mode artifacts
  --output-dir PATH           Run output directory
  --json                      Machine-readable JSON output (stdout)
```

- Without `--json`: rich visual pipeline display on stderr
- With `--json`: machine-readable JSON on stdout, plain progress on stderr
- Exit code 0 = success, 1 = error

### Run artifacts

Each run produces an immutable directory:

```
uploads/runs/<run_id>/
  manifest.json
  input/
    requirement.txt
    source_files/
    ontology.json
    simulation_config.json   # includes taxonomy-driven scenario buckets under event_config
  graph/
    graph.json
    graph_summary.json
  simulation/
    timeline.json
    top_agents.json
    actions.jsonl
    config.json
  report/
    meta.json
    summary.json
    report.md
  eval/
    run_eval.v1.json       # repo-local completed-run evaluation sidecar
  forecast/
    forecast.v1.json       # emitted only for completed runs with persisted canonical brief lineage
  visuals/
    swarm-overview.svg
    cluster-map.svg
    timeline.svg
    platform-split.svg
  logs/
    run.log
    llm_telemetry.jsonl      # per-call Claude/Codex telemetry when CLI runs set AGENTCY_LLM_TELEMETRY_FILE
```

## LLM providers

Set `LLM_PROVIDER` in `.env`:

| Provider | Config | Cost |
|----------|--------|------|
| `claude-cli` | `LLM_PROVIDER=claude-cli` (default) | Uses your Claude Code subscription |
| `codex-cli` | `LLM_PROVIDER=codex-cli` | Uses your Codex CLI subscription |

Optional Claude model override:

```bash
LLM_PROVIDER=claude-cli CLAUDE_MODEL=haiku agentcy-forecast run --files docs/memo.md --requirement "Predict reaction" --smoke --json
```

## Architecture

```
app/
    cli.py             CLI entry point (primary interface)
    cli_display.py     Rich visual pipeline display
    config.py          Environment + validation
    run_artifacts.py   Immutable run storage
    run_eval.py        Repo-local completed-run evaluation sidecar
    smoke_mode.py      Deterministic smoke-mode timeline/report builder
    visual_snapshots.py SVG snapshot generation
    core/              Workbench session, session registry, resource loader, tasks
    resources/         Adapters for projects, documents, graph, simulations, reports
    tools/             Composable pipeline (ingest, build, prepare, run, report)
    services/
      graph_storage.py      JSON graph backend
      graph_db.py           Graph query facade
      entity_extractor.py   LLM-based extraction
      graph_builder.py      Ontology -> graph pipeline
      simulation_runner.py  OASIS simulation orchestration + monitoring
      report_agent.py       Fast report path + legacy ReACT path
      graph_tools.py        Public GraphToolsService assembly point
      graph_models.py       Search/interview result models
      graph_retrieval.py    Base graph CRUD + summaries
      graph_search_tools.py Higher-level search helpers
      graph_interview.py    Agent interview helpers
    utils/
      llm_client.py        CLI-only LLM client (claude-cli, codex-cli)
  scripts/             OASIS simulation runner scripts
```

## Canonical forecast export seam

`agentcy forecast runs export <run_id> --json` is the stable export seam for downstream tooling.

For completed runs, the returned artifact map includes:

- `run_eval` → absolute path to `eval/run_eval.v1.json`

For completed runs that were created from canonical `brief.v1` input, the returned artifact map also includes:

- `forecast_v1` → absolute path to `forecast/forecast.v1.json`

The repo-local `run_eval` file is intentionally internal: it summarizes run shape, top-agent concentration, report/snapshot availability, and synthetic-signal metrics such as coverage, local diversity, complexity, and heuristic critic rejection rate without widening canonical protocol contracts.

The exported `forecast.v1` file is intentionally narrow in loop 3:

- emitted only for completed runs
- carries family lineage (`forecast_id`, `brief_id`, `brand_id`) plus upstream lineage from the imported brief
- keeps MiroFish-local IDs (`project_id`, `graph_id`, `simulation_id`, `report_id`) under `provenance`
- does not force canonical failed/partial forecast shapes yet; those remain repo-local/internal

## Acknowledgments

- [MiroFish](https://github.com/666ghj/MiroFish) by 666ghj — original project
- [OASIS](https://github.com/camel-ai/oasis) by CAMEL-AI — multi-agent social simulation framework

## License

AGPL-3.0
