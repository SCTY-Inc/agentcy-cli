# CLAUDE.md — agentcy monorepo

Agent CLI suite. Five modules + one TypeScript runtime, chained through a shared protocol layer.

## Structure

```
src/agentcy/
├── cli.py              # single entry point
├── persona/            # persona management — create, test, optimize, export
├── brand/              # brand ops — signals → plan → produce → publish
├── forecast/           # swarm prediction — docs + requirement → social forecast
├── metrics/            # measurement + calibration — run_result.v1 → performance.v1
└── protocols/          # shared schemas, adapters, utilities
    ├── schemas/        # JSON schema files (brief.v1, forecast.v1, etc.)
    ├── examples/       # canonical fixture examples
    └── adapters/       # cross-artifact transformers

studio/                 # content studio — draft, render, publish (TypeScript)
└── runtime/
    └── src/
        ├── brands/     # brand.md + design.md loader
        ├── render/     # image (social.ts, card.ts) + video (kino compositions)
        ├── publish/    # platform adapters (Twitter, LinkedIn, Meta, Threads)
        └── runtime/    # SQLite-backed run engine

tests/                  # all tests (mirrors src/agentcy/ structure)
tools/
└── extract-design/     # headless design.md extractor (puppeteer-core)
```

## Pipeline

```
agentcy persona --json export <persona> --to voice-pack.v1             → voice_pack.v1
agentcy brand plan run "<brief>" --brand <id> --json                   → brief.v1
agentcy forecast run --files docs/ --brief brief.v1.json --json        → forecast.v1
agentcy studio run social.post --brand <id> --brief-file ... --json    → run_result.v1
agentcy metrics adapt --run-result ... --sidecar ... --json            → performance.v1
agentcy metrics calibrate --forecast ... --performance ... --json      → calibration
```

Each module reads a protocol artifact from the prior step and emits one for the next.

Pipeline orchestration: `agentcy pipeline run/update/study --json`

## Setup

```bash
uv sync --group dev                      # Python
uv sync --all-extras --group dev         # with optional deps
cd studio/runtime && pnpm install        # TypeScript (studio)

make check                               # run all tests
make test member=brand                   # single module
make pipeline brand=givecare persona=my-persona files=docs/ req="predict adoption" sidecar=sidecar.json
```

## Toolchain

- Python: uv (`pyproject.toml` at root, single package)
- TypeScript: pnpm (standalone in `studio/runtime/`)
- Lint: ruff (Python), tsc + vitest (TypeScript)
- Video: Remotion (in `studio/runtime/src/render/video/`)

## Protocol contracts

All inter-module contracts live in `src/agentcy/protocols/schemas/`:
- `brief.v1.schema.json` — brand → forecast, studio
- `forecast.v1.schema.json` — forecast → metrics calibrate
- `run_result.v1.schema.json` — studio → metrics adapt
- `performance.v1.schema.json` — metrics adapt output; metrics calibrate input
- `voice_pack.v1.schema.json` — persona → brand, studio

## Agent composition

Modules expose clean Python APIs for direct import:

```python
from agentcy.persona import Persona, bootstrap_from_description
from agentcy.brand import load_brand_profile, plan
from agentcy.forecast.config import Config
from agentcy.metrics import adapt_canonical_run_result_to_performance
from agentcy.protocols import SCHEMAS, load_json
```

## Standard interface

- `agentcy doctor --json` — suite-wide readiness
- `agentcy catalog --json` — member ownership + positioning
- `agentcy quickstart --profile ... --json` — install guidance
- `agentcy pipeline run/update/study --json` — pipeline orchestration
- Exit: `0` success, `1` user error, `2` runtime error

## Brand specs

Each brand has two files in `studio/brands/<name>/`:
- `brand.md` — identity, voice, pillars, offers, channels (YAML frontmatter)
- `design.md` — palette, typography, layout, video props (frontmatter) + style, composition, texture, image prompt (markdown body)

## Guardrails

- `git add <files>` never `.`
- forecast's `camel-oasis==0.2.5` / `camel-ai==0.2.78` stay pinned — do not upgrade
- prefer `agentcy forecast run --smoke` for fast e2e artifact proof on Python 3.12
- Never delete `forecast/uploads/runs/` — artifacts are immutable products

## Writer contract split

Canonical artifact lineage keeps legacy `writer.repo` values (stable protocol identifiers):
- `voice_pack.v1` → `{ repo: "cli-prsna", module: "agentcy-vox" }`
- `brief.v1` → `{ repo: "brand-os", module: "agentcy-compass" }`
- `forecast.v1` → `{ repo: "cli-mirofish", module: "agentcy-echo" }`
- `run_result.v1` → `{ repo: "cli-phantom", module: "agentcy-loom" }`
- `performance.v1` → `{ repo: "cli-metrics", module: "agentcy-pulse" }`
