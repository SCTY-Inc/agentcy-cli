# AGENTS.md

Agentcy monorepo: protocol-first brand and content CLI suite. Brand, voice, visual, content, and outcomes are the durable foundation; member runtimes turn it into explicit protocol artifacts. New capabilities should be extensions over the foundation, not new cores.

Read before structural changes: [`docs/capability-model.md`](docs/capability-model.md), [`docs/principal-patterns.md`](docs/principal-patterns.md), [`docs/design-md-fidelity.md`](docs/design-md-fidelity.md).

## Members

| Dir | Bin | Role |
| --- | --- | --- |
| `protocols/` | (lib) | Shared schemas, adapters, helpers (`agentcy-protocols`) |
| `voice/` | `agentcy-voice` | Personas: create, test, optimize, export `voice_pack.v1` |
| `briefs/` | `agentcy-briefs` | Brand kit + prompt to `brief.v1` |
| `forecast/` | `agentcy-forecast` | Docs + requirement to `forecast.v1` |
| `studio/` | `agentcy-studio` (TypeScript) | Brief to draft, render, publish (`run_result.v1`) |
| `measure/` | `agentcy-measure` | `run_result.v1` to `performance.v1`, calibration, study |

Each member has its own `AGENTS.md` (local commands, layout, gotchas). Do not add component-level `CLAUDE.md` files.

## Setup and checks

```bash
uv sync --group dev
cd studio && pnpm install     # also needed by protocol seam tests

make check-python             # pytest across all members
make check-studio             # vitest + tsc
make lint                     # ruff on maintained surfaces
agentcy doctor --json         # root smoke
```

Forecast full simulation: `make install-forecast-simulation` (isolated Python 3.11 env).

## Pipeline

Default core: `brief.v1` then deterministic Studio artifacts. Voice, Forecast, publish, Measure are opt-in.

```
agentcy-briefs plan run "<brief>" --brand <id> --brief-v1-output brief.json -f json
agentcy studio run social.post --brand <id> --brief-file brief.json --json
agentcy-voice --json export <persona> --to voice-pack.v1
agentcy-forecast run --files docs/ --brief brief.json --json
agentcy-measure adapt --run-result run_result.json --sidecar sidecar.json --output performance.json
```

`agentcy pipeline run|update|study` orchestrates these and writes a manifest under `artifacts/pipelines/<pipeline_id>/`. Root `--provider` / `--model` are forwarded to members that honor them.

## Contracts

Schemas live in `protocols/`: `brief.v1` (Briefs to Forecast, Studio), `forecast.v1` (Forecast to Measure), `run_result.v1` (Studio to Measure), `performance.v1` (Measure), `voice_pack.v1` (Voice to Briefs, Studio). Each artifact's `writer.repo` and `writer.module` carry the same `agentcy-*` name; Python imports use underscores.

CLI exit codes: `0` success, `1` user error, `2` runtime error. JSON envelopes differ per member; use each tool's documented form, or `agentcy member <member> --json ...` for a normalized envelope.

## Rules

- Keep changes lean, explicit, verifiable. Prefer machine-readable CLI modes for verification.
- Keep writer lineage aligned with current schemas; no legacy names.
- Do not stage or commit unless asked. Do not touch unrelated dirty files.
- Forecast simulation pins `camel-oasis==0.2.5` / `camel-ai==0.2.78` (`forecast/requirements-simulation.txt`); do not upgrade.
- Prefer `agentcy-forecast run --smoke` for fast e2e proof (no LLM calls; output has `"smoke": true`, no `confidence`; plumbing check, not a prediction).
- Never delete `forecast/uploads/runs/`; run artifacts are immutable.
- Personas: `voice/personas/*.yaml` (override with `AGENTCY_PERSONAS_DIR`). Brand kits: `brands/<name>/{BRAND.md, DESIGN.md, brand.yml, assets/}`; Studio finds them by walking up from CWD.
- `agentcy-measure calibrate` is the single calibration surface.
- Social credentials on the atum server belong to `atelier/publish`; do not run agentcy publishers against `/home/deploy/.env` there.
