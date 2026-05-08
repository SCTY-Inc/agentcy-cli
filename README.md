# agentcy

Agent CLI suite — five Python modules + one TypeScript runtime, chained through a shared protocol layer.

## Structure

```
src/agentcy/
├── persona/       persona management — create, test, optimize, export
├── brand/         brand ops — signals → plan → produce → publish
├── forecast/      swarm prediction — docs + requirement → forecast
├── metrics/       measurement + calibration + study
├── protocols/     shared schemas, adapters, utilities
├── extract/       headless design.md extractor (puppeteer-core)
└── cli.py         single CLI entry point

studio/            content studio — draft, render, publish (TypeScript)
└── runtime/       brand loader, image + video render, platform publish

tests/             all tests
```

## Pipeline

```
agentcy persona → voice_pack.v1
agentcy brand   → brief.v1
agentcy forecast → forecast.v1
agentcy studio  → run_result.v1
agentcy metrics → performance.v1 → calibration
```

Each module reads a protocol artifact from the prior step and emits one for the next.

## Setup

```bash
uv sync --group dev                  # Python
cd studio/runtime && pnpm install    # TypeScript
```

## Usage

```bash
# CLI
agentcy persona --json export scientist --to voice-pack.v1
agentcy brand plan run "launch post" --brand givecare --json
agentcy forecast run --files docs/ --brief brief.v1.json --json
agentcy studio run social.post --brand givecare --json
agentcy metrics adapt --run-result run.json --sidecar s.json --json

# Pipeline orchestration
agentcy pipeline run --persona scientist --brand givecare \
  --brief "Before fall gets busy, make caregiving feel lighter" \
  --files docs/ --json

# Agent composition (direct imports)
from agentcy.persona import Persona
from agentcy.brand import load_brand_profile, plan
from agentcy.protocols import SCHEMAS, load_json
```

## Test

```bash
make check          # all tests (Python + TypeScript)
make test member=brand   # single module
make lint           # ruff
```

## Video rendering (kino)

Remotion compositions in `studio/runtime/src/render/video/`. Renders brand-driven social videos:

```bash
cd studio/runtime
npx remotion render givecare-landscape out/givecare.mp4
npx remotion render scty-vertical out/scty.mp4
```

## Design token extraction

```bash
node src/agentcy/extract/extract.mjs https://example.com --out design.md
```

## Install profiles

```bash
uv sync --group dev                          # base suite
uv sync --extra persona --group dev          # + persona deps (dspy, litellm)
uv sync --extra brand-all --group dev        # + all brand extras
uv sync --extra forecast-simulation          # + OASIS simulation (Python 3.11)
uv sync --all-extras --group dev             # everything
cd studio/runtime && pnpm install            # TypeScript runtime
```

## Protocol contracts

Schemas in `src/agentcy/protocols/schemas/`:

| Schema | From | To |
|--------|------|----|
| `voice_pack.v1` | persona | brand, studio |
| `brief.v1` | brand | forecast, studio |
| `forecast.v1` | forecast | metrics |
| `run_result.v1` | studio | metrics |
| `performance.v1` | metrics | metrics (calibrate) |

## Writer contract

Protocol lineage keeps legacy `writer.repo` values (stable identifiers):

```
voice_pack.v1  → { repo: "cli-prsna",    module: "agentcy-vox" }
brief.v1       → { repo: "brand-os",     module: "agentcy-compass" }
forecast.v1    → { repo: "cli-mirofish", module: "agentcy-echo" }
run_result.v1  → { repo: "cli-phantom",  module: "agentcy-loom" }
performance.v1 → { repo: "cli-metrics",  module: "agentcy-pulse" }
```
