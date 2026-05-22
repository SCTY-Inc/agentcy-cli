# CLAUDE.md — agentcy monorepo

Agent CLI suite. Brand, voice, visual, content, and outcomes form the durable foundation; member runtimes transform that foundation through a shared protocol layer. New capabilities should usually be extensions over this foundation, not new product cores.

Source-of-truth docs:

- [`docs/capability-model.md`](docs/capability-model.md) — foundation, runtimes, extensions, product rule
- [`docs/principal-patterns.md`](docs/principal-patterns.md) — small-core operating model
- [`docs/design-md-fidelity.md`](docs/design-md-fidelity.md) — `DESIGN.md` evidence-first visual contract

## Members

| Dir | Bin | Role |
|-----|-----|------|
| `protocols/` | (lib) | Shared schemas + adapters + narrow helper utilities — `agentcy-protocols` pip package |
| `voice/` | `agentcy-voice` | Persona management — create, test, optimize, export |
| `briefs/` | `agentcy-briefs` | Brand ops — signals → plan → produce → publish |
| `forecast/` | `agentcy-forecast` | Swarm prediction — docs + requirement → social forecast |
| `studio/` | `agentcy-studio` | Comms runtime — brief → draft → render → publish (TypeScript) |
| `measure/` | `agentcy-measure` | Measurement + calibration + study — run_result.v1 → performance.v1 |

## Pipeline

```
agentcy-briefs plan run "<brief>" --brand <id> --voice-pack-id <brand>.voice.default \
  --brief-v1-output <brief.v1.json> -f json                                      → brief.v1
agentcy-studio run social.post --brand <id> --brief-file brief.v1.json --json      → inspectable Studio artifacts
```

That is the default core. Voice, Forecast, publish, and Measure are opt-in extensions:

```
agentcy-voice --json export <persona> --to voice-pack.v1                           → voice_pack.v1
agentcy-forecast run --files docs/ --brief brief.v1.json --json                    → forecast.v1
agentcy-studio publish <run_id> --json                                             → run_result.v1
agentcy-measure adapt --run-result ... --sidecar ... --output performance.v1.json  → performance.v1
```

The root dispatcher now also exposes a lightweight pipeline layer:
- `agentcy pipeline run ...` persists a pipeline manifest under `artifacts/pipelines/<pipeline_id>/manifest.json`, writes a module-first bundle, supports stable named folders via `--pipeline-id`, and defaults to `brief.v1` plus deterministic Studio artifacts
- `agentcy pipeline run` does not run Voice, Forecast, publish, Measure, or provider-backed image generation by default
- use `--persona`, `--persona-eval`, `--with-forecast --files ...`, and `--publish` to turn on heavier stages explicitly
- `agentcy pipeline update --manifest ... --run-result ... --performance ...` backfills later-stage canonical artifact paths after Studio publish / Measure adapt finish
- `agentcy pipeline study --manifest ...` reopens that manifest and runs `agentcy-measure study` with auto-discovered forecast / voice eval sidecars
- root `--provider` and `--model` flags are forwarded as `LLM_PROVIDER` / `CLAUDE_MODEL` to members that support them; the pipeline layer also maps compatible values onto Briefs as `BRANDOPS_LLM_PROVIDER` / `BRANDOPS_LLM_MODEL`

## Setup

```bash
# Python tools + repo-local dev commands
uv sync --group dev

# TypeScript Studio runtime (under studio/)
cd studio && pnpm install
# Protocol seam tests call the Studio launcher, so this install is also required for `make check-python`

# Legacy Echo full simulation runtime, isolated on Python 3.11
make install-forecast-simulation

# Full live pipeline (requires make install-forecast-simulation + make install-studio)
make pipeline brand=givecare persona=my-persona files=docs/ req="predict adoption" sidecar=sidecar.json

# GiveCare-specific pipeline targets
make pipeline-givecare req="your brief" files=docs/          # live run
make pipeline-givecare-preview req="your brief"              # smoke + dry publish

# Fixture-backed downstream smoke path
make pipeline-fixtures sidecar=protocols/tests/fixtures/run_result_to_performance_v1/sidecar.rich.json
```

## Toolchain

- Python: uv workspace (`pyproject.toml` at root)
- TypeScript: pnpm for Studio (standalone in `studio/`)
- Lint: ruff (Python), tsc + vitest (TypeScript)

## Protocol contracts

All inter-tool contracts live in `protocols/`:
- `brief.v1.schema.json` — Briefs → Forecast, Studio
- `forecast.v1.schema.json` — Forecast → Measure calibrate
- `run_result.v1.schema.json` — Studio → Measure adapt
- `performance.v1.schema.json` — Measure adapt output; Measure calibrate input
- `voice_pack.v1.schema.json` — Voice → Briefs, Studio

## Standard interface

Current operator contract:
- `agentcy doctor --json` returns the normalized suite-wide readiness envelope
- `agentcy catalog --json` returns foundation, extension, member ownership, install profile, and positioning metadata in one root envelope
- `agentcy quickstart --profile ... --json` returns the smallest install path for a chosen suite profile
- `agentcy-measure --json` now emits `{"status": "ok"|"error", "command": str, "data": {...}}` for `adapt`, `calibrate`, `study`, and `doctor`
- `agentcy-voice` uses a global `--json` flag
- `agentcy-forecast` and `agentcy-studio` expose subcommand-level `--json`
- `agentcy pipeline run/update/study --json` emit root-level normalized envelopes
- `agentcy member <member> --json ...` wraps any member in one normalized root envelope, even when the member's native JSON contract differs
- `agentcy-briefs` now exposes a global `--json` preference across compatible data-producing commands, plus `--json-envelope` for normalized Compass-local success envelopes
- Exit: `0` success, `1` user error, `2` runtime error

Do not assume every member subcommand has the same JSON envelope yet; use the documented command form for each tool.

## Guardrails

- `trash` not `rm`
- `git add <files>` never `.`
- Forecast's simulation env keeps `camel-oasis==0.2.5` / `camel-ai==0.2.78` pinned in `forecast/requirements-simulation.txt` — do not upgrade
- prefer `agentcy-forecast run --smoke` when you need a fast e2e artifact proof on Python 3.12 or when the live OASIS runtime is too slow for validation; smoke now fully skips ontology/graph/profiles — no LLM calls
- CLI automation for full Forecast runs should exit cleanly on its own; command-waiting mode is for debug/service workflows, not the operator happy path
- Never delete `forecast/uploads/runs/` — artifacts are immutable products
- Persona authoring/testing/export lives in `agentcy-voice`; Briefs has no persona surface
- `agentcy-measure calibrate` is the single calibration surface (absorbed legacy `agentcy-lab`)
- Voice personas live in `voice/personas/*.yaml`; the CLI reads them directly from the repo (override via `AGENTCY_PERSONAS_DIR` if needed)
- Brand kits live at `brands/<name>/{BRAND.md, DESIGN.md, brand.yml, assets/}` at the repo root; Studio auto-detects by walking up from CWD looking for `brands/<id>/BRAND.md`
- Forecast smoke `forecast.v1` emits `"smoke": true` and omits `confidence` — treat these forecasts as plumbing checks, not real predictions

## Canonical writer pairs

Each protocol artifact carries the same `agentcy-*` name in both `writer.repo` and `writer.module`:
- `voice_pack.v1` → `agentcy-voice`
- `brief.v1` → `agentcy-briefs`
- `forecast.v1` → `agentcy-forecast`
- `run_result.v1` → `agentcy-studio`
- `performance.v1` → `agentcy-measure`

Python module imports match these names (with underscores): `agentcy_voice`, `agentcy_briefs`, `agentcy_forecast`, `agentcy_pulse` (for `agentcy-measure`).
