# Studio Runtime

TypeScript runtime for Agentcy content generation, rendering, review, and publishing.

## Scope

The active runtime supports four workflows:

- `social.post`
- `blog.post`
- `outreach.touch`
- `respond.reply`

Everything flows through the same primitives:

1. signal
2. brief
3. draft
4. review
5. publish

## Commands

```bash
cd runtime
agentcy-studio help
agentcy-studio ops health --json
agentcy-studio brand validate givecare --json
agentcy-studio brand validate brands/givecare/BRAND.md --json
agentcy-studio run social.post --brand givecare --topic "caregiver benefits gap" --json
agentcy-studio run blog.post --brand givecare --pillar policy --topic "paid leave" --json
agentcy-studio review list --json
agentcy-studio review approve <run_id> --variant social-main --json
agentcy-studio inspect run <run_id> --json
agentcy-studio publish <run_id> --platforms twitter,linkedin --dry-run --json
agentcy-studio lab cover --brand givecare --title "Care is infrastructure" --subtitle "Make invisible work visible." --json
```

Direct bin (also valid):

```bash
agentcy-studio help
agentcy-studio help --json
```

## Architecture

- `runtime/src/domain/` — typed workflow, run, and artifact model
- `runtime/src/brands/` — strict foundation loader for `BRAND.md` / `<brand>.brand.md` plus optional `DESIGN.md`
- `runtime/src/runtime/` — SQLite-backed runtime and workflow engine
- `runtime/src/commands/` — public CLI commands
- `brands/<brand>/BRAND.md` — tenant behavioral brand contract for agents
- `brands/<brand>/DESIGN.md` — optional Google `design.md` visual-system sidecar with Agentcy source evidence, artifact mappings, image grammar, composition, and fidelity gates under `agentcy`
- `state/` — runtime database, artifacts, and exports, generated on demand and gitignored

## Principles

- one runtime, four workflows
- tenant `BRAND.md` and optional `DESIGN.md` contracts are loaded at command boundaries
- typed artifacts between every step
- SQLite-backed state
- resumable runs
- explicit failed-run state with stored error messages
- approval before publish
- fail-fast validation at command boundaries
- deterministic lab outputs for share-card and OG-cover experiments
- no legacy content pipeline or brand foundation assumptions in the active code path

## Notes

- The previous implementation has been archived under `archive/legacy-20260325/`.
- Legacy outputs and unused package leftovers were moved under `archive/legacy-20260325/legacy-artifacts/`.
- CLI help and the active social workflow now start even when the optional native `canvas` binding is missing; social rendering falls back to SVG/resvg in that case.
