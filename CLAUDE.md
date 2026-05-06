# CLAUDE.md — agentcy monorepo

Agent CLI suite. Six tools that chain sequentially through a shared protocol layer.

## Members

| Dir | Bin | Role |
|-----|-----|------|
| `protocols/` | (lib) | Shared schemas + adapters + narrow helper utilities — `agentcy-protocols` pip package |
| `vox/` | `agentcy-vox` | Persona management — create, test, optimize, export |
| `compass/` | `agentcy-compass` | Brand ops — signals → plan → produce → publish |
| `echo/` | `agentcy-echo` | Swarm prediction — docs + requirement → social forecast |
| `loom/` | `agentcy-loom` | Comms runtime — brief → draft → render → publish (TypeScript) |
| `pulse/` | `agentcy-pulse` | Measurement + calibration + study — run_result.v1 → performance.v1 |

## Pipeline

```
agentcy-vox --json export <persona> --to voice-pack.v1                                → voice_pack.v1
agentcy-compass plan run "<brief>" --brand <id> --voice-pack-input <voice_pack> \
  --brief-v1-output <brief.v1.json> -f json                                           → brief.v1
agentcy-echo run --files docs/ --brief brief.v1.json --json                           → forecast.v1
agentcy-loom run social.post --brand <id> --brief-file brief.v1.json --json           → run_result.v1
agentcy-pulse adapt --run-result ... --sidecar ... --output performance.v1.json --json → performance.v1
agentcy-pulse calibrate --forecast ... --performance ... --json                        → calibration
```

Each tool reads a protocol artifact from the prior step and emits one for the next.

The root dispatcher now also exposes a lightweight pipeline layer:
- `agentcy pipeline run ...` persists a pipeline manifest under `artifacts/pipelines/<pipeline_id>/manifest.json`, writes a module-first bundle (`vox/`, `compass/`, `echo/`, `loom/`, `pulse/`, `reports/`), supports stable named folders via `--pipeline-id`, can save `--persona-eval`, and can optionally kick off `--loom-workflow ...`
- `agentcy pipeline run --mode preview` auto-approves/publishes loom as a dry run and writes an honest `pulse/preview.json` note instead of pretending a canonical `performance.v1` exists
- `agentcy pipeline update --manifest ... --run-result ... --performance ...` backfills later-stage canonical artifact paths after loom publish / pulse adapt finish
- `agentcy pipeline study --manifest ...` reopens that manifest and runs `agentcy-pulse study` with auto-discovered forecast / echo / persona sidecars
- root `--provider` and `--model` flags are forwarded as `LLM_PROVIDER` / `CLAUDE_MODEL` to members that support them; the pipeline layer also maps compatible values onto Compass as `BRANDOPS_LLM_PROVIDER` / `BRANDOPS_LLM_MODEL`

## Setup

```bash
# Python tools + repo-local dev commands
uv sync --group dev

# Optional extras
uv sync --all-extras --group dev

# TypeScript (loom)
cd loom/runtime && pnpm install
# Protocol seam tests call the loom launcher, so this install is also required for `make check-python`

# Install vox personas to ~/.prsna/personas/ (required after editing vox/personas/*.yaml)
make install-personas

# Full live pipeline (echo simulation requires Python 3.11 + simulation extra)
make pipeline brand=givecare persona=my-persona files=docs/ req="predict adoption" sidecar=sidecar.json

# GiveCare-specific pipeline targets
make pipeline-givecare req="your brief" files=docs/          # live run
make pipeline-givecare-preview req="your brief"              # smoke + dry publish

# Fixture-backed downstream smoke path
make pipeline-fixtures sidecar=protocols/tests/fixtures/run_result_to_performance_v1/sidecar.rich.json
```

## Toolchain

- Python: uv workspace (`pyproject.toml` at root)
- TypeScript: pnpm (standalone in `loom/runtime/`)
- Lint: ruff (Python), tsc + vitest (TypeScript)

## Protocol contracts

All inter-tool contracts live in `protocols/`:
- `brief.v1.schema.json` — compass → echo, loom
- `forecast.v1.schema.json` — echo → pulse calibrate
- `run_result.v1.schema.json` — loom → pulse adapt
- `performance.v1.schema.json` — pulse adapt output; pulse calibrate input
- `voice_pack.v1.schema.json` — vox → compass, loom

## Standard interface

Current operator contract:
- `agentcy doctor --json` returns the normalized suite-wide readiness envelope
- `agentcy catalog --json` returns suite/member ownership, install profiles, and positioning metadata in one root envelope
- `agentcy quickstart --profile ... --json` returns the smallest install path for a chosen suite profile
- `agentcy-pulse --json` now emits `{"status": "ok"|"error", "command": str, "data": {...}}` for `adapt`, `calibrate`, `study`, and `doctor`
- `agentcy-vox` uses a global `--json` flag
- `agentcy-echo` and `agentcy-loom` expose subcommand-level `--json`
- `agentcy pipeline run/update/study --json` emit root-level normalized envelopes
- `agentcy member <member> --json ...` wraps any member in one normalized root envelope, even when the member's native JSON contract differs
- `agentcy-compass` now exposes a global `--json` preference across compatible data-producing commands, plus `--json-envelope` for normalized Compass-local success envelopes
- Exit: `0` success, `1` user error, `2` runtime error

Do not assume every member subcommand has the same JSON envelope yet; use the documented command form for each tool.

## Guardrails

- `trash` not `rm`
- `git add <files>` never `.`
- echo's `camel-oasis==0.2.5` / `camel-ai==0.2.78` stay pinned — do not upgrade
- prefer `agentcy-echo run --smoke` when you need a fast e2e artifact proof on Python 3.12 or when the live OASIS runtime is too slow for validation; smoke now fully skips ontology/graph/profiles — no LLM calls
- CLI automation for full echo runs should exit cleanly on its own; command-waiting mode is for debug/service workflows, not the operator happy path
- Never delete `echo/uploads/runs/` — artifacts are immutable products
- compass persona subcommands are deprecated — use `agentcy-vox` instead
- pulse absorbs lab: `agentcy-pulse calibrate` replaces `agentcy-lab calibration`
- vox personas source from `vox/personas/*.yaml` but install to `~/.prsna/personas/`; run `make install-personas` after editing persona files
- loom brands live at `loom/runtime/brands/<name>/BRAND.md`; set `LOOM_ROOT` or rely on the pipeline's auto-inject when running from monorepo root
- `agentcy pipeline run` auto-sets `LOOM_ROOT=loom/runtime` so loom resolves brands correctly from any CWD
- echo smoke `forecast.v1` emits `"smoke": true` and omits `confidence` — treat these forecasts as plumbing checks, not real predictions

## Writer contract split

Canonical artifact lineage intentionally keeps legacy `writer.repo` values while package/bin names use `agentcy-*`:
- `voice_pack.v1` → `{ repo: "cli-prsna", module: "agentcy-vox" }`
- `brief.v1` → `{ repo: "brand-os", module: "agentcy-compass" }`
- `forecast.v1` → `{ repo: "cli-mirofish", module: "agentcy-echo" }`
- `run_result.v1` → `{ repo: "cli-phantom", module: "agentcy-loom" }`
- `performance.v1` → `{ repo: "cli-metrics", module: "agentcy-pulse" }`

## Module names (Python imports unchanged)

Bins renamed; Python import paths preserved until explicit refactor:
- compass imports: `brand_os`
- echo imports: `app`
- pulse imports: `agentcy_pulse`
- vox imports: `prsna`
