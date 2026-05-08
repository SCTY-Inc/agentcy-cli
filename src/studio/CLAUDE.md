# agentcy studio

Content studio — draft, render, publish. Brand specs (`brand.md` + `design.md`) drive voice, visual identity, and platform targeting. TypeScript runtime, part of the agentcy monorepo.

## Surfaces

- npm package: `agentcy-loom` (historical name, kept for compatibility)
- CLI: `agentcy studio ...` via dispatcher, or `node bin/loom.js` directly
- Video: Remotion compositions in `runtime/src/render/video/` (kino)
- Writer contract: `run_result.v1.writer = { repo: "cli-phantom", module: "agentcy-loom" }`

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
agentcy studio help
agentcy studio ops health --json
agentcy studio brand validate givecare --json
agentcy studio auto --brand givecare --json
agentcy studio auto --brand scty --topic "AI adoption gap" --dry-run --json
agentcy studio run social.post --brand givecare --topic "caregiver benefits gap" --json
agentcy studio run social.post --brand givecare --auto-approve --json
agentcy studio run social.post --brand givecare --format infographic --topic "caregiver workforce" --json
agentcy studio run social.post --brand givecare --pillar care-economy --topic "$470B unpaid care labor" --json
agentcy studio run blog.post --brand givecare --pillar policy --topic "paid leave" --json
agentcy studio review list --json
agentcy studio review approve <run_id> --variant social-main --json
agentcy studio publish <run_id> --platforms twitter,linkedin --dry-run --json
agentcy studio inspect run <run_id> --json
agentcy studio retry <run_id> --from draft --json
agentcy studio lab render --brand givecare --figure statement --gravity high --ground cream --platform linkedin --headline "Care is infrastructure" --body "63M provide unpaid care." --image watershed --json
```

Packaged-proof target for loop 8 once install metadata work begins:

```bash
# from outside the repo root after local package install
agentcy studio --help
agentcy studio help --json
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
      card.ts      deterministic proportional card renderer (lab)
      social.ts    two-phase social renderer (Gemini art + deterministic text composite; canvas optional)
      dither.ts    procedural art subjects + Bayer 4×4 dithering
      colors.ts    shared color math (hexToRgb, muted)
      fonts.ts     shared font registration (idempotent)
    runtime/     SQLite-backed run engine + step definitions

brands/
  <name>/brand.md + design.md         agent operating spec (see below)
  <name>/learnings.json    card vocabulary, visual system learnings

state/          generated at runtime, gitignored
archive/        archived legacy + generate-card.sh
```

## Brand Spec (brand.md + design.md)

brand.md + design.md is the agent's operating instructions:

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
3. **Render** — two-phase: Gemini generates art-only image (no text/logos via `image_prompt` with `[SUBJECT]` slot), then the runtime composites typography + logo deterministically. The preferred path uses native canvas when available, with an SVG/resvg fallback when it is not. Per-platform assets (Twitter 16:9, LinkedIn 1:1, Facebook 1:1, Instagram 4:5, Threads 4:5).

Requires `GEMINI_API_KEY` or `GOOGLE_API_KEY`. Without keys, copy falls back to templates and images fall back to deterministic generated backgrounds. CLI startup and `help --json` no longer require native canvas to be installed.

## Card Renderer (lab render)

Proportional typographic system for the interactive card lab. Three inputs → PNG:

- **Figure**: `statement` (headline), `stat` (big number), `passage` (quote), `index` (stacked list)
- **Gravity**: `high`, `center`, `low` — shifts content within Renner margin ratios (2:3:4:6)
- **Ground**: 12 color schemes (cream, warm, slate, sage, grounded, mute, ink, dusk, dawn, ember, fog, storm)

All sizes from √2 modular scale. Dithered abstract imagery (topography, watershed, strata, grid-erosion, root-system, threshold) on right side, non-overlapping with text. Outputs to `state/cards/`.

```bash
agentcy studio lab render --brand givecare --figure stat --gravity center --ground grounded --platform linkedin --stat-num '$1T' --stat-label 'unpaid care labor' --image strata --json
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
