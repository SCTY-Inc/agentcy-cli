# agentcy

A creative CLI suite for brand work: voice, briefs, forecasting, studio drafts, and measurement, connected by explicit protocol artifacts.

```bash
uv tool install git+https://github.com/SCTY-Inc/agentcy-cli
agentcy --help
```

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/). The `studio` runtime also needs Node 22+. Licensed MIT.

Consolidated monorepo for the Agentcy CLI suite. Member runtimes transform a durable Brand / Voice / Visual / Content / Outcomes foundation into explicit protocol artifacts.

Read these first:

- [`docs/capability-model.md`](docs/capability-model.md) — foundation, runtimes, extensions
- [`docs/principal-patterns.md`](docs/principal-patterns.md) — small-core operating model
- [`docs/design-md-fidelity.md`](docs/design-md-fidelity.md) — `DESIGN.md` evidence-first visual contract

A portable brand kit lives at `brands/<brand>/{BRAND.md, DESIGN.md, brand.yml, assets/}`. `BRAND.md` is the behavioral contract; `DESIGN.md` follows Google's public `design.md` shape under `design_system` / `tokens` / `components`, with Agentcy execution rules under `agentcy`.

## Members

| Dir | Package / bin | Purpose |
| --- | --- | --- |
| `protocols/` | `agentcy-protocols` | Shared schemas, examples, and adapters |
| `voice/` | `agentcy-voice` | Persona creation and `voice_pack.v1` export |
| `briefs/` | `agentcy-briefs` | Brand planning and `brief.v1` generation |
| `forecast/` | `agentcy-forecast` | Forecast generation from documents + requirement |
| `studio/` | `agentcy-studio` | TypeScript execution runtime for `brand.md`-driven drafts, review, publish |
| `measure/` | `agentcy-measure` | `run_result.v1` → `performance.v1` + calibration + study |

## Naming contract

Each protocol artifact's `writer.repo` and `writer.module` carry the same `agentcy-*` name. Python imports match with underscores (`agentcy_voice`, `agentcy_briefs`, `agentcy_forecast`, `agentcy_measure`).

## Capabilities and extensions

See [`docs/capability-model.md`](docs/capability-model.md) for the canonical model.

Current extension families:

- Studio generation: `social.post`, `blog.post`, `outreach.touch`, `respond.reply`, lab card/cover/render
- Forecasting: audience/social reaction forecasts and repo-local `run_eval` sidecars
- Measurement: `adapt`, `calibrate`, `study`
- Agent instructions: one nested `skills/agentcy` skill with reference files

Natural next Studio modes are `og.cover`, `social.card`, `carousel`, `short.video`, `ugc.ad`, `longform.script`, and `campaign.pack`.

## Setup

```bash
# Python workspace + repo-local dev tools
uv sync --group dev

# Studio runtime (under studio/)
cd studio && pnpm install

# Forecast full simulation runtime, isolated on Python 3.11
make install-forecast-simulation
```

## Best fit

Agentcy is best when you need a protocol-first workflow stack rather than a single embedded SDK:

- brand kit → brief → Studio artifacts by default, with Voice/Forecast/Measure as opt-in extensions
- multi-tenant brand execution from agent-facing `BRAND.md` contracts
- human-and-agent collaboration over stable JSON/file handoffs
- resumable operator workflows with explicit artifacts and lineage

It is not yet the best fit for:

- non-technical one-click onboarding
- teams that only want a single import-and-go library

## Install profiles

The suite is consumable in layers:

```bash
# Base Python suite: root CLI + protocols + voice + briefs + forecast base CLI + measure
uv sync --group dev
# or: make install-python-suite

# Full Forecast simulation runtime (isolated Python 3.11 env)
make install-forecast-simulation

# Studio runtime (Node, under studio/)
cd studio && pnpm install
# or: make install-studio

# Full local operator stack
make install-full-operator
```

Published package contours:

- `agentcy-protocols` — closest thing to a drop-in library layer
- `agentcy-*` member CLIs — stage-owned workflow tools
- `agentcy` — umbrella dispatcher and pipeline orchestrator

The umbrella package is therefore best understood as an operator CLI suite, not a single drop-in SDK.

Useful discovery commands:

```bash
agentcy catalog --json
agentcy quickstart --profile full-operator --json
agentcy doctor --json
agentcy member briefs --json plan list
```

## Test it

```bash
make doctor
make check
make lint
```

### Direct test commands

```bash
# The protocol seam tests shell into studio, so install the runtime once in a clean checkout.
cd studio && pnpm install

uv run pytest tests briefs/tests forecast/tests measure/tests voice/tests protocols/tests -q
cd studio && pnpm check
```

## Pipeline commands

### Root pipeline helpers

```bash
# Essential bundle: cheap deterministic output under artifacts/pipelines/<pipeline_id>/
uv run agentcy pipeline run \
  --pipeline-id givecare-launch-01 \
  --brand givecare \
  --brief "Before fall gets busy, make caregiving feel lighter" \
  --mode preview \
  --output-dir artifacts/pipelines \
  --json

# Default path:
# brief.v1 -> Studio draft/render -> inspectable artifacts
# It does not run Voice, Forecast, Measure, providers, or publish unless requested.

# Heavier opt-in path
uv run agentcy --provider claude-cli --model sonnet pipeline run \
  --pipeline-id givecare-launch-forecast-01 \
  --brand givecare \
  --brief "Before fall gets busy, make caregiving feel lighter" \
  --persona scientist \
  --persona-eval \
  --with-forecast \
  --files docs/launch-memo.md \
  --publish \
  --smoke \
  --output-dir artifacts/pipelines \
  --json

# After Studio publish + Measure adapt happen, backfill the bundle with canonical later-stage artifacts
uv run agentcy pipeline update \
  --manifest artifacts/pipelines/<pipeline_id>/manifest.json \
  --run-result /tmp/run_result.json \
  --performance /tmp/performance.json \
  --json

# Re-open the manifest later and run Measure study once performance exists
uv run agentcy pipeline study \
  --manifest artifacts/pipelines/<pipeline_id>/manifest.json \
  --json
```

Dispatcher commands also accept root-level LLM overrides that are forwarded to members which honor them. The root pipeline also supports `--pipeline-id` so stable bundles can land at paths like `artifacts/pipelines/givecare-launch-01/`:

```bash
uv run agentcy --provider claude-cli --model haiku forecast run --files docs/memo.md --requirement "Predict reaction" --smoke --json
```

### Live pipeline

```bash
uv run agentcy-voice --json export scientist --to voice-pack.v1 > /tmp/voice_pack.json
uv run agentcy-briefs plan run "Before fall gets busy, make caregiving feel lighter" \
  --brand givecare \
  --voice-pack-input /tmp/voice_pack.json \
  --brief-v1-output /tmp/brief.json \
  -f json > /tmp/brief_plan.json
forecast/.venv-simulation/bin/agentcy-forecast run --files docs/ --brief /tmp/brief.json --json > /tmp/forecast.json
uv run agentcy studio run social.post --brand givecare --brief-file /tmp/brief.json --json > /tmp/run_result.json
uv run agentcy-measure adapt --run-result /tmp/run_result.json --sidecar sidecar.json --output /tmp/performance.json --json > /tmp/performance.stdout.json
uv run agentcy-measure calibrate --forecast /tmp/forecast.json --performance /tmp/performance.json --json > /tmp/calibration.json
```

### Runtime constraints

- `agentcy-forecast` full simulation requires `make install-forecast-simulation`, which creates `forecast/.venv-simulation` on Python 3.11
- `agentcy-forecast run --smoke` skips ontology/graph/profiles and the OASIS subprocess, then emits deterministic run artifacts for plumbing checks
- Studio runtime under `studio` needs `pnpm install`
- `make pipeline-fixtures` is the fixture-backed smoke path when you only want to validate downstream protocol plumbing

## Current status

- Root dispatcher: healthy, probes member reachability, exposes `pipeline run` / `pipeline update` / `pipeline study`, defaults to Briefs mock provider plus deterministic Studio artifacts, forwards root-level `--provider` / `--model` overrides when explicitly provided, and exposes `agentcy member <member> --json ...` as a normalized wrapper over member-local JSON differences
- Voice: structured eval tiers and saved eval-report review flow now ship in the CLI
- Briefs: healthy for package/CLI + planning surfaces, supports provider/model forwarding, and exposes both `--json` preference and `--json-envelope` normalized success envelopes
- Forecast: base CLI healthy; completed runs emit a repo-local `run_eval` sidecar alongside canonical forecast export; full simulation still requires the isolated Python 3.11 env
- Studio: social rendering is deterministic SVG/resvg with no Gemini/image-provider dependency in the default workflow; lab card/cover/render are the first visible extension surfaces
- Measure: supports standardized `--json` envelopes and a `study` command that ingests optional forecast/voice eval sidecars
