# Loom Runtime

First-principles rebuild of the repo as a brand communications runtime.

## Naming policy

Canonical surfaces (monorepo):

- repo: `agentcy`
- npm package: `agentcy-loom`
- installed CLI: `agentcy-loom`
- dispatcher alias: `agentcy loom ...`
- canonical artifact writer: `run_result.v1.writer = { repo: "cli-phantom", module: "agentcy-loom" }`

The runtime is Agentcy-branded at the package/bin layer, but canonical protocol lineage still keeps the historical `writer.repo` value for compatibility.

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
agentcy loom help
agentcy loom ops health --json
agentcy loom brand validate givecare --json
agentcy loom run social.post --brand givecare --topic "caregiver benefits gap" --json
agentcy loom run blog.post --brand givecare --pillar policy --topic "paid leave" --json
agentcy loom review list --json
agentcy loom review approve <run_id> --variant social-main --json
agentcy loom inspect run <run_id> --json
agentcy loom publish <run_id> --platforms twitter,linkedin --dry-run --json
```

Direct bin (also valid):

```bash
agentcy-loom help
agentcy-loom help --json
```

## Architecture

- `runtime/src/domain/` — typed workflow, run, and artifact model
- `runtime/src/brands/` — brand foundation loader
- `runtime/src/runtime/` — SQLite-backed runtime and workflow engine
- `runtime/src/commands/` — public CLI commands
- `brands/<brand>/brand.yml` — brand foundations, including pillars, visual system, handles, and playbooks
- `state/` — runtime database, artifacts, and exports, generated on demand and gitignored

## Principles

- one runtime, four workflows
- typed artifacts between every step
- SQLite-backed state
- resumable runs
- explicit failed-run state with stored error messages
- approval before publish
- fail-fast validation at command boundaries
- no legacy content pipeline assumptions in the active code path

## Notes

- The previous implementation has been archived under `archive/legacy-20260325/`.
- Legacy outputs and unused package leftovers were moved under `archive/legacy-20260325/legacy-artifacts/`.
- CLI help and the active social workflow now start even when the optional native `canvas` binding is missing; social rendering falls back to SVG/resvg in that case.
