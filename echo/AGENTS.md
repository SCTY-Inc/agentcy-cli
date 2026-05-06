# AGENTS.md — agentcy-echo

Echo is the CLI-only swarm prediction member. It consumes documents plus a requirement or `brief.v1`, then emits forecast artifacts.

## Current Surfaces

- Python distribution: `agentcy-echo`
- Python import root: `app`
- installed CLI: `agentcy-echo`
- dispatcher alias: `agentcy echo ...`
- writer contract: `forecast.v1.writer = { repo: "cli-mirofish", module: "agentcy-echo" }`

## Commands

```bash
uv sync
uv sync --extra simulation
agentcy echo run --files f.pdf --requirement "..." --json
agentcy echo run --files f.pdf --requirement "..." --smoke --json
agentcy echo runs list --json
agentcy echo runs status <id> --json
agentcy echo runs export <id> --json
uv run python -m pytest -x
```

## Layout

```text
app/
  cli.py              Typer entry point
  run_artifacts.py    immutable run storage
  run_eval.py         repo-local completed-run evaluation sidecar
  smoke_mode.py       deterministic smoke-mode timeline/report builder
  core/               WorkbenchSession, TaskManager, ResourceLoader
  tools/              ontology, graph, prepare, run, report steps
  services/           graph, simulation, report, and LLM services
scripts/              OASIS subprocess runners
uploads/              runtime data, gitignored
data/                 graph JSON storage, gitignored
```

## Gotchas

- `camel-oasis==0.2.5` and `camel-ai==0.2.78` stay pinned.
- Prefer `--smoke` for fast artifact proof or Python 3.12 validation. Smoke now fully bypasses ontology/graph/profiles — no LLM calls, deterministic 3-agent stub. Previously `--smoke` still called the LLM for ontology; that bug is fixed.
- Smoke `forecast.v1` emits `"smoke": true` and omits `confidence` — do not treat as a real forecast.
- `brief_path` parameter in `_run_pipeline()` fixed — was referencing undefined `args` variable (now uses the `brief` param directly).
- Full simulation automation starts the subprocess with `--no-wait`.
- JSON mode bypasses rich display; rich output goes through stderr.
- Never delete `uploads/runs/`; run artifacts are immutable products.
