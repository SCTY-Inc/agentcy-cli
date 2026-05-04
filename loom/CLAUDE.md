# agentcy-loom

Autonomous brand communications agent. brand.yml is the operating spec — pillars are lenses for evaluating signals, voice constrains copy, visual drives rendering, offers define CTAs. The runtime executes the spec. Member of the agentcy monorepo.

## Current surfaces (monorepo)

- npm package: `agentcy-loom`
- CLI bin: `agentcy-loom` (via `bun bin/loom.js`)
- dispatcher alias: `agentcy loom ...`
- writer contract: `run_result.v1.writer = { repo: "cli-phantom", module: "agentcy-loom" }`

The package and CLI are Agentcy-branded, but canonical protocol lineage still keeps the historical `writer.repo` value for compatibility.

## Active Surface

The active CLI lives in `runtime/src/cli.ts`.

Supported workflows:

- `social.post`
- `blog.post`
- `outreach.touch`
- `respond.reply`

Core commands:

```bash
cd runtime
agentcy loom help
agentcy loom ops health --json
agentcy loom brand validate givecare --json
agentcy loom auto --brand givecare --json
agentcy loom auto --brand scty --topic "AI adoption gap" --dry-run --json
agentcy loom run social.post --brand givecare --topic "caregiver benefits gap" --json
agentcy loom run social.post --brand givecare --auto-approve --json
agentcy loom run social.post --brand givecare --format infographic --topic "caregiver workforce" --json
agentcy loom run social.post --brand givecare --pillar care-economy --topic "$470B unpaid care labor" --json
agentcy loom run blog.post --brand givecare --pillar policy --topic "paid leave" --json
agentcy loom review list --json
agentcy loom review approve <run_id> --variant social-main --json
agentcy loom publish <run_id> --platforms twitter,linkedin --dry-run --json
agentcy loom inspect run <run_id> --json
agentcy loom retry <run_id> --from draft --json
agentcy loom lab render --brand givecare --figure statement --gravity high --ground cream --platform linkedin --headline "Care is infrastructure" --body "63M provide unpaid care." --json
```

Packaged-proof target for loop 8 once install metadata work begins:

```bash
# from outside the repo root after local package install
agentcy loom --help
agentcy loom help --json
```

Treat those commands as the readiness gate for package/CLI work. They are not evidence that the repo itself has been renamed.

## CLI Rules

Agentic CLI contract:

- non-interactive by default
- all inputs available via flags
- `--json` for machine-readable results
- useful `--help` with examples
- fail fast with actionable messages
- idempotent or resumable side effects

## Structure

```text
runtime/
  src/
    brands/      brand foundation loader
    cli/         command dispatch
    commands/    public command handlers
    core/        paths, env helpers
    domain/      workflow/run/artifact types
    generate/    LLM copy drafts (Gemini), explore grid, source image
    publish/     social platform adapters (Twitter, LinkedIn, Meta, Threads)
    render/
      gemini.ts    shared Gemini API (generateText + generateImage)
      tokens.ts    design governance — parses brand.design.md, exports typed constants
      template.ts  Satori element tree — all card layout/typography (no canvas, no JSX)
      pipeline.ts  compose: Gemini art → Satori SVG → resvg PNG; renderCard() is the public API
    runtime/     SQLite-backed run engine + step definitions

brands/
  <name>/brand.yml         agent operating spec (see below)
  <name>/learnings.json    card vocabulary, visual system learnings

state/          generated at runtime, gitignored
archive/        archived legacy + generate-card.sh
```

## Brand Spec (brand.yml)

brand.yml is the agent's operating instructions:

- **pillars** — what the agent talks about + from what angle (lenses, not calendar)
- **voice** — tone, style, do/don't rules for copy generation
- **visual** — palette, typography, image_prompt (Agnes Martin for GiveCare), style
- **offers** — products with `url` and `cta` (e.g., "Sign up at pulse.givecareapp.com")
- **channels** — where content goes, `platforms` list, `default_offer` for CTA resolution

CTA resolution: `channels.social.default_offer` → matches `offers[].id` → uses that offer's `cta` field. No hallucinated CTAs.

## Social Post Pipeline

Two modes:

- **`auto`** — signal-to-publish in one shot (auto-approve + publish). Cron entry point.
- **`run`** — generates content, lands in `in_review`. Use `--auto-approve` to skip review gate.

Pipeline steps: `signal → brief → draft → explore → image → render`

1. **Signal** — topic from `--topic` flag, or auto-discovered via Gemini from brand pillar signals when omitted.
2. **Draft** — LLM-generated copy via Gemini using brand voice rules as prompt constraints. Falls back to templates without API key.
3. **Render** — `renderCard()` in `render/pipeline.ts`: Gemini generates background art (no text/logos), Satori renders the typographic layer deterministically, resvg converts to PNG. No native addons. Per-platform assets: linkedin 1:1, twitter 16:9, instagram 4:5, facebook 1:1, threads 4:5. Null Gemini key → solid ground color fallback.

Requires `GEMINI_API_KEY` or `GOOGLE_API_KEY`. Without keys, copy falls back to templates and cards render with solid ground color only.

## Card Renderer (lab render)

Typographic card system defined in `brand.design.md` (governance) and rendered via Satori (zero native deps). Three inputs → PNG:

- **Figure**: `statement` (headline), `stat` (big number), `passage` (quote), `index` (stacked list)
- **Gravity**: `high`, `center`, `low` — shifts content anchor within Renner margin ratios (2:3:4:6)
- **Ground**: 12 color schemes (cream, warm, slate, sage, grounded, mute, ink, dusk, dawn, ember, fog, storm)

All sizes from √2 modular scale (base = 1% of canvas width). Left 5/8 is text panel (solid ground color), right 3/8 is generative art zone. Outputs to `state/cards/`.

Note: `--image` flag (dither art subject) is removed — background art is now Gemini-generated.

```bash
agentcy loom lab render --brand givecare --figure stat --gravity center --ground grounded --platform linkedin --stat-num '$1T' --stat-label 'unpaid care labor' --image strata --json
```

## Content Pillars

Each brand defines pillars with `perspective`, `signals`, `format`, and `frequency`. The runtime uses these as lenses — matching signals to pillars, injecting perspective into copy, and accepting `--pillar <id>` to force an angle.

## Output Formats

Per-brand formats via `--format <id>`. Resolution: explicit flag → pillar's `default_format` → `standard`.

Each format can define `prompt_overlay` for copy generation variation (e.g., infographic format extracts stats).

## Runtime Safety

- failed runs persisted with step and error message
- published runs cannot be reviewed again
- explicit publish targets must be configured for the brand
- `inspect artifact` limited to files under `state/artifacts/`

## Verification

```bash
cd runtime
npx vitest run
npx tsc --noEmit
```

## Archive

Legacy content-pipeline: `archive/legacy-20260325/`. Standalone generate-card.sh: `archive/generate-card.sh`.
