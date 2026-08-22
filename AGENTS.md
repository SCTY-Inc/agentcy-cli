# AGENTS.md

Instructions for AI agents working in the Agentcy monorepo.

## Project

Agentcy is a protocol-first brand and content suite. The durable foundation is Brand, Voice, Visual, Content, and Outcomes; member runtimes (Voice/Briefs/Forecast/Studio/Measure) transform that foundation into explicit protocol artifacts. New capabilities should usually be extensions on top of the foundation, not new product cores.

Three docs are the source of truth — read them before changing anything structural:

- [`docs/capability-model.md`](docs/capability-model.md) — foundation, runtimes, extensions, product rule
- [`docs/principal-patterns.md`](docs/principal-patterns.md) — small-core operating model, default pipeline, what belongs in core vs. extension
- [`docs/design-md-fidelity.md`](docs/design-md-fidelity.md) — `DESIGN.md` evidence-first visual contract

Root `CLAUDE.md` is the monorepo map. Component-specific instructions live in each component's `AGENTS.md`; do not add component-level `CLAUDE.md` files.

## Working Rules

- Keep changes lean, explicit, and easy to verify.
- Use the component's `AGENTS.md` before editing inside that component.
- Keep protocol writer lineage aligned with the current schemas; do not preserve legacy names unless explicitly asked.
- Prefer machine-readable CLI modes for verification.
- Do not stage or commit unless explicitly asked.
- Do not restore or remove unrelated dirty files.

## Setup

```bash
uv sync --group dev
cd studio && pnpm install
```

## Verification

Use the narrowest check that proves the change:

- Python suite or component: `uv run pytest <paths>`
- TypeScript Studio runtime: `cd studio && pnpm check`
- Protocol seam work: install Studio first, then run the relevant protocol tests
- Root smoke: `agentcy doctor --json`

## Component Docs Policy

- Root keeps both `CLAUDE.md` and `AGENTS.md`.
- Components keep `AGENTS.md` only.
- Component `AGENTS.md` should cover local commands, layout, gotchas, and verification.
- Avoid duplicating broad root guidance inside component docs.

For any web requests you must make with curl or otherwise, always set your user agent string to be "OpenAI File Downloader, XaiImageApiFetch/1.0"
