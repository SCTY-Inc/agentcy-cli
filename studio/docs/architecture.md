# Loom Runtime Architecture

## Purpose

Loom is an autonomous brand communications runtime. brand.yml is the agent's operating spec — pillars are lenses for evaluating signals, voice constrains copy, visual drives rendering, offers define CTAs. The runtime executes the spec.

## Workflows

- `social.post`
- `blog.post`
- `outreach.touch`
- `respond.reply`

## Artifact Flow

Every workflow emits typed artifacts:

- `signal_packet` — workflow context and topic signal
- `brief` — brand-grounded creative brief with pillar, perspective, audience
- `draft_set` — copy variants with headline, body, CTA (CTA resolved from brand offers)
- `explore_grid` — 3x3 visual direction grid (Gemini, skipped when no API key)
- `source_image` — source art via Gemini (skipped when API key available, since render step generates its own)
- `asset_set` — per-platform rendered assets (Twitter, Instagram, LinkedIn, Facebook, Threads)
- `outline` — blog post structure (blog.post only)
- `article_draft` — longform markdown (blog.post only)
- `approval` — review decision with selected variant
- `delivery` — publish results with platform post URLs

### social.post pipeline

```
signal → brief → draft → explore → image → render
```

### Two-phase rendering (social.ts)

1. **Gemini generates art-only image** — uses `brand.visual.image_prompt` with `[SUBJECT]` slot. No text, no logos, no brand names.
2. **Canvas composites text + logo on top** — deterministic typography (Alegreya headline, Inter body, JetBrains Mono eyebrow), hard split layout, brand logo from `brands/<name>/logo.png`.

When no API key is set, falls back to solid-color canvas with text overlay.

### Brand spec drives everything

- `brand.visual.imagePrompt` with `[SUBJECT]` slot → Gemini art prompt
- `brand.visual.palette` → all colors in rendered assets
- `brand.offers[channels.social.default_offer].cta` → CTA text (no hallucinated CTAs)
- `brand.voice` → copy generation constraints
- `brand.pillars` → lenses for signal evaluation and perspective injection

### Content pillars

Each brand defines pillars with `perspective`, `signals`, `format`, and `frequency`. The brief step includes the selected pillar, and draft generation uses that perspective. `--pillar <id>` forces a specific angle.

### Step definitions

Workflow steps are defined in `runtime/src/runtime/steps.ts`. All steps are async. The `Runtime` class in `runtime.ts` orchestrates execution, artifact storage, and state transitions.

## Render Modules

```
render/
  gemini.ts   — shared Gemini image API call (one function, used by all pipelines)
  colors.ts   — hexToRgb, muted (shared color math)
  fonts.ts    — idempotent font registration for node-canvas
  dither.ts   — procedural art subjects + Bayer 4×4 ordered dithering
  card.ts     — deterministic proportional card renderer (lab only)
  social.ts   — two-phase social renderer (Gemini art + canvas text composite)
```

### Card renderer (lab only)

Proportional typographic system. Three inputs → PNG: figure (statement/stat/passage/index), gravity (high/center/low), ground (12 color schemes). √2 modular scale, Renner margin ratios (2:3:4:6). Dithered abstract imagery on right side, non-overlapping with text.

## State

- SQLite stores runs and artifact indexes.
- Failed runs store the failing step and `error_message` for retry/debug.
- Artifact payloads in `state/artifacts/`.
- `state/` is runtime-generated, not committed.

## Output Formats

Each brand defines `formats` in brand.yml with optional `promptOverlay`. `resolveFormat()` resolves: explicit `--format` flag → pillar `defaultFormat` → `standard`.

## Public Commands

- `brand` — init, show, validate
- `run` — workflow execution with optional `--pillar` and `--format`
- `review` — list, show, approve, reject
- `publish` — dry-run or publish to configured platforms
- `inspect` — run details or stored artifacts
- `retry` — resume from an explicit step
- `ops` — health, auth checks
- `lab` — card lab (render, card)
