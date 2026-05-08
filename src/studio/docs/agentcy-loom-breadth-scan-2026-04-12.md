# cli-phantom breadth scan — brief.v1 / run_result.v1 deferral scorecard

Date: 2026-04-12
Scope: documentation-only repo scan for future `agentcy-loom` protocol boundaries.

## Current runtime surface

Primary runtime: `runtime/src/cli.ts`

Supported workflows:
- `social.post`
- `blog.post`
- `outreach.touch`
- `respond.reply`

Core orchestration path:
- command handlers in `runtime/src/commands/`
- workflow definitions in `runtime/src/runtime/steps.ts`
- run state + artifact persistence in `runtime/src/runtime/runtime.ts`
- shared types in `runtime/src/domain/types.ts`
- SQLite schema in `runtime/src/runtime/db.ts`

## Current artifact types

Defined in `runtime/src/domain/types.ts`:

| Artifact type | Produced by | Current role |
| --- | --- | --- |
| `signal_packet` | `signal` step | normalized workflow/topic context |
| `brief` | `brief` step | brand-grounded execution brief used by downstream draft logic |
| `draft_set` | `draft` step | variant set for social/outreach/respond |
| `explore_grid` | `explore` step | visual-direction exploration grid for social |
| `source_image` | `image` step | source image metadata or skipped marker |
| `asset_set` | `render` step | rendered per-platform assets for social |
| `outline` | `outline` step | blog structure |
| `article_draft` | `draft` step in `blog.post` | markdown article |
| `approval` | `review` step | review decision + selected variant |
| `delivery` | `publish` step | publish/export outcomes |

## Current run states

Defined in `runtime/src/domain/types.ts` as `RunStatus`:
- `in_review`
- `approved`
- `rejected`
- `published`
- `failed`

Observed state transitions in `runtime/src/runtime/runtime.ts`:

### Normal authoring path
1. `runWorkflow()` creates run
2. `executeWorkflow()` advances through workflow steps while keeping status `in_review`
3. final pre-publish state:
   - `in_review` by default
   - `approved` when `autoApprove` is used
4. `reviewRun()` changes state to `approved` or `rejected`
5. `publishRun()` changes state to:
   - `published` on full success
   - `approved` on social dry-run
   - `approved` on partial social publish failure

### Failure path
- any step error in `executeWorkflow()` -> status `failed`
- failing step stored in `current_step`
- message stored in `error_message`
- failed runs must be retried before review

### Retry path
- `retryRun()` creates a new child run with `parent_run_id`
- artifacts before the selected retry step are copied forward
- new retry run re-enters `in_review`

## Workflow-local artifact stacks

### `social.post`
`signal_packet -> brief -> draft_set -> explore_grid -> source_image -> asset_set`

Publish-time add-ons:
- `approval`
- `delivery`

### `blog.post`
`signal_packet -> brief -> outline -> article_draft`

Publish-time add-on:
- `delivery` with markdown export path under `state/exports/`

### `outreach.touch`
`signal_packet -> brief -> draft_set`

### `respond.reply`
`signal_packet -> brief -> draft_set`

## Internal state and storage surfaces

Persistent runtime surfaces today:
- `state/loom.sqlite` — run rows + artifact index rows
- `state/artifacts/<run_id>/*.json` — per-artifact payloads
- `state/exports/` — exported publish outputs like blog markdown

Important run fields already present for future protocol mapping:
- `id`
- `workflow`
- `brand`
- `status`
- `input`
- `currentStep`
- `createdAt`
- `updatedAt`
- `parentRunId`
- `errorMessage`

## Thinnest likely future `brief.v1` ingestion point

Best thin seam: **the boundary immediately before or inside `buildBriefArtifacts()` in `runtime/src/runtime/steps.ts`.**

Why this is the thinnest seam:
- all workflows already converge on a single `brief` artifact type
- downstream steps already consume `brief` as the canonical context object
- this avoids rewiring draft/render/publish logic first
- it keeps `agentcy-loom` as the execution owner while allowing `agentcy-compass` to become the external writer of `brief.v1`

Practical future shapes, from thinnest to thicker:

1. **Best deferral target:** add an optional prebuilt brief input to `run` commands, then normalize it into the existing internal `brief` artifact shape before draft steps run.
2. allow `signal_packet` + external brief side-by-side, with external brief taking precedence when present.
3. later, promote the internal `brief` artifact shape into a formal `brief.v1` adapter/validator.

Most likely files for that future change:
- `runtime/src/commands/run.ts`
- `runtime/src/runtime/steps.ts`
- `runtime/src/domain/types.ts`
- possibly a new adapter file such as `runtime/src/domain/brief-v1.ts`

## Natural future `run_result.v1` boundary

Best thin seam: **the `delivery` artifact plus final run row returned by `publishRun()` in `runtime/src/runtime/runtime.ts`.**

Why this is the natural output boundary:
- publish/export outcomes are already consolidated there
- `delivery` already holds platform results, selected variant, dry-run flag, export paths, and simulated status
- final run state (`published`, `approved`, `failed`) lives alongside it and should remain loom-owned
- this keeps `run_result.v1` focused on execution outcome instead of every internal generation artifact

Recommended future `run_result.v1` envelope should likely include:
- `run_id`
- `parent_run_id`
- `workflow`
- `brand_id`
- `brief_id` or external lineage reference when present
- `status`
- `current_step`
- `review_decision` summary if present
- `delivery` payload / publish results
- timestamps, including a stable completion timestamp for downstream measurement joins
- carried lineage fields when present (`source_voice_pack_id`, `campaign_id`, `signal_id`)
- optional error summary when status is `failed`

### Loop-5 pulse seam lock

For the current bounded `run_result.v1 -> performance.v1` seam, treat only **published `social.post`** outcomes as pulse measurement sources.

That means the loom-owned export must preserve, at minimum:
- `run_id`
- `brief_id`
- `brand_id`
- `workflow`
- `completed_at`
- per-platform publish locator entries with `platform`, plus `post_id` and `url` when the adapter provides them
- carried lineage: `source_voice_pack_id`, `campaign_id`, `signal_id`

Explicit exclusions for loop 5:
- `dry_run` results are review/operator artifacts, not pulse measurement sources
- `failed` results are debugging artifacts, not pulse measurement sources
- non-`social.post` workflows stay out of `performance.v1` v1 even when exported as valid loom artifacts

This keeps the seam loom-local and protocol-first: no analytics collection, no `cli-metrics` bootstrap, and no cross-family runtime rewiring is required to prove the locator handoff.

What should stay internal for now:
- raw intermediate artifacts like `explore_grid`, `source_image`, and `asset_set`
- internal artifact file paths under `state/artifacts/`
- renderer-specific details unless needed for debugging

## Deferral scorecard

### Ready enough to anchor later
- typed artifact registry already exists
- run statuses are explicit and test-covered
- one runtime owner for run state is clear
- review and publish stages are already separated
- retry lineage via `parent_run_id` already exists

### Still internal / not worth formalizing yet
- current `brief` payload is execution-friendly but not yet a family protocol contract
- `delivery` shape is close to a protocol boundary but still social/blog-flow specific
- no explicit external lineage fields yet (`brief_id`, `voice_pack_id`, etc.)
- no schema validator or adapter layer for imported/exported protocol versions

## Likely files to touch in a future protocol pass

Documentation / schema:
- `docs/architecture.md`
- parent-level protocol docs and canonical examples outside this repo

Repo-local implementation:
- `runtime/src/domain/types.ts`
- `runtime/src/runtime/steps.ts`
- `runtime/src/runtime/runtime.ts`
- `runtime/src/commands/run.ts`
- `runtime/src/commands/publish.ts`
- `runtime/src/runtime/runtime.test.ts`

Potential new files:
- `runtime/src/domain/brief-v1.ts`
- `runtime/src/domain/run-result-v1.ts`
- protocol fixture files for example payloads/tests

## Repo-local mirror fixture note

For repo-local seam documentation and smoke-test convenience only, `cli-phantom/runtime/fixtures/run_result.v1.published.mirror.json` mirrors the current canonical published example from `../protocols/examples/run_result.v1.published.json`.

Guardrails for that mirror fixture:
- it is a labeled mirror/reference fixture only, not a second authority
- `protocols/examples/run_result.v1.published.json` remains the sole canonical source fixture for the loop-6 seam
- the mirror adds no analytics logic, attribution logic, or pulse ownership claims inside `cli-phantom`
- family-owned loop-6 seam proof stays in parent docs/examples/tests and does not depend on this repo-local copy

## Verification commands for this scan and future boundary work

Current repo verification:

```bash
cd cli-phantom/runtime
npm test
npx tsc --noEmit
npx tsx src/cli.ts help
npx tsx src/cli.ts ops health --json
```

Useful runtime behavior checks:

```bash
cd cli-phantom/runtime
npx tsx src/cli.ts run social.post --brand givecare --topic "caregiver benefits gap" --json
npx tsx src/cli.ts review list --json
npx tsx src/cli.ts inspect run <run_id> --json
npx tsx src/cli.ts publish <run_id> --platforms twitter,linkedin --dry-run --json
npx tsx src/cli.ts retry <run_id> --from draft --json
```

## Bottom line

`cli-phantom` is already close to the desired `agentcy-loom` boundary.

- The **input seam** to defer toward is the internal `brief` artifact creation point.
- The **output seam** to defer toward is the `delivery` artifact plus final run record.
- The runtime already has enough typed state and lineage scaffolding to support later `brief.v1 -> run_result.v1` adapters without a broad rewrite.
