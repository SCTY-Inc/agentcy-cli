# AGENTS.md

Instructions for AI agents working in the Agentcy monorepo.

## Project

Agentcy is a protocol-first CLI suite. Members chain through stable artifacts:

- `vox/` creates and evaluates personas, emitting `voice_pack.v1`
- `compass/` plans brand work, emitting `brief.v1`
- `echo/` forecasts likely social response, emitting `forecast.v1`
- `loom/` executes brand communications from `BRAND.md`, emitting `run_result.v1`
- `pulse/` adapts and studies outcomes, emitting `performance.v1`
- `protocols/` owns shared schemas, adapters, and fixtures

Root `CLAUDE.md` is the monorepo map. Component-specific instructions live in each component's `AGENTS.md`; do not add component-level `CLAUDE.md` files.

## Working Rules

- Keep changes lean, explicit, and easy to verify.
- Use the component's `AGENTS.md` before editing inside that component.
- Preserve canonical writer lineage even when package names use `agentcy-*`.
- Prefer machine-readable CLI modes for verification.
- Do not stage or commit unless explicitly asked.
- Do not restore or remove unrelated dirty files.

## Setup

```bash
uv sync --group dev
cd loom/runtime && pnpm install
```

## Verification

Use the narrowest check that proves the change:

- Python suite or component: `uv run pytest <paths>`
- TypeScript Loom runtime: `cd loom/runtime && pnpm check`
- Protocol seam work: install Loom first, then run the relevant protocol tests
- Root smoke: `agentcy doctor --json`

## Component Docs Policy

- Root keeps both `CLAUDE.md` and `AGENTS.md`.
- Components keep `AGENTS.md` only.
- Component `AGENTS.md` should cover local commands, layout, gotchas, and verification.
- Avoid duplicating broad root guidance inside component docs.
