# Agentcy canonical lineage rules

Status: authoritative family protocol artifact for the current family protocol slices (`voice_pack.v1 -> brief.v1`, `brief.v1 -> run_result.v1`, `brief.v1 -> forecast.v1`, and published `social.post` `run_result.v1 -> performance.v1`)
Date: 2026-04-12

## Authority and ownership

These parent-level protocol artifacts are authoritative for the family:

- `protocols/voice_pack.v1.schema.json`
- `protocols/brief.v1.schema.json`
- `protocols/lineage-rules.md`
- `protocols/run_result.v1.schema.json`
- `protocols/examples/*.json`

Repo-local fixtures should mirror these validated examples.
They should not redefine the contract.

Writer ownership for the active family protocol surfaces remains explicit:
`brand-os` remains the sole canonical writer for `brief.v1` in loop 4; `cli-agency` may inform strategy and research concepts but must not appear as a `brief.v1` writer or protocol authority.

| Artifact | Canonical writer repo | Family module |
| --- | --- | --- |
| `voice_pack.v1` | `cli-prsna` | `agentcy-vox` |
| `brief.v1` | `brand-os` | `agentcy-compass` |
| `run_result.v1` | `cli-phantom` | `agentcy-loom` |
| `forecast.v1` | `cli-mirofish` | `agentcy-echo` |
| `performance.v1` | `cli-metrics` / future repo | `agentcy-pulse` |

## Naming rule for lineage IDs

All lineage IDs in this first slice are lowercase strings matching:

```text
^[a-z0-9][a-z0-9._-]{2,127}$
```

Recommended shape:

```text
<brand>.<artifact>.<descriptor>.<version-or-date>
```

Examples:

- `givecare.brand.core`
- `givecare.voice.default.v1`
- `givecare.brief.launch_fall_checkin.2026-04-12`

Rules:

1. IDs are stable references, not human display names.
2. Use lowercase only.
3. Preserve the same `brand_id` across all artifacts for one brand lineage.
4. A new materially distinct artifact gets a new artifact ID rather than mutating history in place.

## Field rules

### `brand_id`

`brand_id` identifies the brand lineage shared by all first-slice artifacts.

Rules:

1. `brand_id` is required in both `voice_pack.v1` and `brief.v1`.
2. A `brief.v1.brand_id` must exactly equal the `brand_id` of the `voice_pack.v1` it references.
3. `brand_id` is family-stable across multiple voice packs and briefs for the same brand.
4. A writer may enrich metadata around a brand locally, but the canonical lineage key is still `brand_id`.

### `voice_pack_id`

`voice_pack_id` identifies a specific canonical voice artifact written by `cli-prsna`.

Rules:

1. `voice_pack_id` is required in `voice_pack.v1` and must be globally unique within the family artifact set.
2. `brief.v1.voice_pack_id` is required and must point at the exact canonical `voice_pack.v1` used to shape the brief.
3. `brief.v1.lineage.source_voice_pack_id`, when present, must equal `brief.v1.voice_pack_id`.
4. If a voice pack changes in a way that would affect downstream interpretation, emit a new `voice_pack_id`.

### `brief_id`

`brief_id` identifies a specific canonical planning artifact written by `brand-os`.

Rules:

1. `brief_id` is required in `brief.v1` and must be globally unique within the family artifact set.
2. `brief_id` is created by the brief writer, not inherited from the voice pack.
3. Many briefs may reference one `voice_pack_id`; the relationship is one-to-many.
4. Downstream artifacts such as `forecast.v1`, `run_result.v1`, and `performance.v1` should reference `brief_id` rather than copying brief contents into lineage.

### `forecast_id`

`forecast_id` identifies one canonical completed forecast artifact written by `cli-mirofish`.

Rules:

1. `forecast_id` is required in `forecast.v1` and is created by the forecast writer, never copied from upstream planning artifacts.
2. `forecast_id` must be globally unique within the family artifact set.
3. Multiple `forecast_id` values may point at the same `brief_id` because one canonical brief may be re-simulated across different forecast windows or model/runtime revisions.
4. `forecast.v1.brief_id` must always point at the exact canonical `brief.v1` artifact the forecast summarizes.

### `run_id`

`run_id` identifies one canonical loom execution outcome written by `cli-phantom`.

Rules:

1. `run_id` is required in `run_result.v1` and is created by the loom runtime, never copied from upstream planning artifacts.
2. `run_id` must be globally unique within the family artifact set.
3. Multiple `run_id` values may point at the same `brief_id` because one brief can be retried, dry-run, or published multiple times.
4. `run_result.v1.brief_id` must always point at the exact canonical `brief.v1` artifact the runtime executed or simulated.

### `parent_run_id`

`parent_run_id` is optional lineage used when one loom run is an explicit retry or continuation of an earlier loom run.

Rules:

1. `parent_run_id` must be absent for a first-attempt run.
2. When present, `parent_run_id` must reference another `run_result.v1.run_id` from the same `brand_id` and `brief_id` lineage.
3. `parent_run_id` is for retry/continuation lineage only; it must not be used to point back to a `brief_id` or upstream artifact.
4. A child retry run gets a fresh `run_id`; retries do not mutate the original run artifact in place.

### `performance_id`

`performance_id` identifies one canonical aggregate measurement snapshot written by future `cli-metrics` / `agentcy-pulse`.

Rules:

1. `performance_id` is required in `performance.v1` and is created by the measurement writer, never copied from upstream planning or runtime artifacts.
2. `performance_id` must be globally unique within the family artifact set.
3. Multiple `performance_id` values may point at the same `run_id` because one published post run can be measured across multiple windows such as `24h-post-publish` and `7d-post-publish`.
4. `performance.v1.run_id` must always point at the exact canonical published `run_result.v1` artifact the measurement snapshot summarizes.

### `forecast.v1` lineage and status semantics

Loop 3 makes an explicit family protocol decision: canonical `forecast.v1` covers completed forecasts only.
Failed, cancelled, partial, or in-progress MiroFish outcomes may still exist as repo-local states, but those shapes are deferred from the parent canonical schema rather than encoded as optional export variants.

Family lineage rules:

1. `forecast.v1.forecast_id` is the family-stable identifier for the completed forecast artifact.
2. `forecast.v1.brief_id` must exactly equal the canonical upstream `brief.v1.brief_id`.
3. `forecast.v1.brand_id` must exactly equal the upstream `brief.v1.brand_id`.
4. `forecast.v1.lineage.source_brief_id` should equal `forecast.v1.brief_id` so the persisted handoff is explicit even when the forecast artifact is viewed alone.
5. When upstream family lineage exists in the imported brief, `source_voice_pack_id`, `campaign_id`, and `signal_id` should be carried through unchanged into `forecast.v1.lineage`.
6. `project_id`, `graph_id`, `simulation_id`, and `report_id` are MiroFish-local provenance identifiers, not family lineage IDs; if exported, they belong under `forecast.v1.provenance`, not under `forecast.v1.lineage`.
7. `forecast.v1.writer` must remain `{ "repo": "cli-mirofish", "module": "agentcy-echo" }` for canonical exports.
8. Non-completed canonical forecast statuses are deferred until a later slice defines them intentionally.

### `run_result.v1` status semantics

`run_result.v1.status` is the canonical family summary of loom execution outcome.

Allowed canonical values:

- `dry_run` — execution reached the delivery/export seam without publishing to external platforms
- `published` — at least one intended platform publish succeeded and the artifact represents a real publish outcome
- `failed` — the run terminated unsuccessfully and includes an error summary

Rules:

1. Dry-run outcomes must be encoded as `dry_run`, not `published`, `approved`, or `skipped`.
2. `published` is only for real external delivery outcomes, not simulations.
3. `failed` must include a stable error summary with the failing step and message.
4. Repo-local internal statuses may be richer, but any exported family artifact must normalize to the canonical `run_result.v1` status set above.
5. `run_result.v1.writer` must remain `{ "repo": "cli-phantom", "module": "agentcy-loom" }` even when the run consumed a `brief.v1` written elsewhere.

### `performance.v1` scope, lineage, and privacy semantics

Loop 5 makes an explicit family protocol decision: canonical `performance.v1` covers aggregate measurement snapshots for published `social.post` outcomes only.
Dry-run, failed, blog, outreach, reply, and non-`social.post` analytics remain deferred rather than being encoded as optional canonical export shapes.

Family lineage and privacy rules:

1. `performance.v1.performance_id` is the family-stable identifier for one measurement snapshot.
2. `performance.v1.run_id` must exactly equal the canonical upstream published `run_result.v1.run_id`.
3. `performance.v1.brief_id` must exactly equal the upstream `run_result.v1.brief_id`.
4. `performance.v1.brand_id` must exactly equal the upstream `run_result.v1.brand_id`.
5. When upstream family lineage exists in the run result, `source_voice_pack_id`, `campaign_id`, and `signal_id` should be carried through unchanged into `performance.v1.lineage`.
6. `performance.v1.writer` must remain `{ "repo": "cli-metrics", "module": "agentcy-pulse" }` for canonical exports.
7. `performance.v1.workflow` must remain `social.post` for this first slice.
8. Each platform observation must include `platform` plus at least one publish locator: `post_id` and/or `url`.
9. Metric fields must stay narrow, aggregate, and optional; canonical examples may include values like `impressions`, `reach`, `engagements`, `likes`, `comments`, `shares`, `saves`, `clicks`, `video_views`, `engagement_rate`, and `ctr`, but should not expand into broad warehouse-shaped payloads.
10. Canonical `performance.v1` artifacts, examples, and tests must include no tokens, secrets, auth material, account credentials, audience-level data, or user-level PII.
11. Publish locators such as platform `post_id` and public `url` are allowed because they identify the published artifact rather than an audience member.
12. While `cli-metrics` is still absent, these pulse rules also function as the minimum birth contract for any future repo: do not widen beyond the canonical published `social.post` seam before repo/package/import/CLI naming is chosen intentionally at repo birth.

## Cross-artifact invariants

These are the canonical invariants for the active family slices:

1. `voice_pack.v1.writer` must be `{ "repo": "cli-prsna", "module": "agentcy-vox" }`.
2. `brief.v1.writer` must be `{ "repo": "brand-os", "module": "agentcy-compass" }`.
2a. No canonical family artifact, example, mirror fixture, or protocol test may restate `cli-agency` as a `brief.v1` writer, alternate writer, or protocol authority.
3. `run_result.v1.writer` must be `{ "repo": "cli-phantom", "module": "agentcy-loom" }`.
4. `performance.v1.writer` must be `{ "repo": "cli-metrics", "module": "agentcy-pulse" }`.
5. `brief.v1.brand_id` must equal the referenced voice pack's `brand_id`.
6. `brief.v1.voice_pack_id` must equal the referenced voice pack's `voice_pack_id`.
7. `run_result.v1.brand_id` must equal the referenced brief's `brand_id`.
8. `run_result.v1.brief_id` must equal the canonical brief artifact it executed.
9. If `run_result.v1.lineage.source_voice_pack_id` is present, it should equal the upstream brief lineage's `source_voice_pack_id`.
10. `forecast.v1.brand_id` must equal the referenced brief's `brand_id`.
11. `forecast.v1.brief_id` must equal the canonical brief artifact it summarizes.
12. If `forecast.v1.lineage.source_voice_pack_id` is present, it should equal the upstream brief lineage's `source_voice_pack_id`.
13. `performance.v1.brand_id` must equal the referenced run result's `brand_id`.
14. `performance.v1.brief_id` must equal the referenced run result's `brief_id`.
15. If `performance.v1.lineage.source_voice_pack_id` is present, it should equal the upstream run result lineage's `source_voice_pack_id`.
16. `forecast.v1.provenance.*` fields must not replace or redefine family lineage semantics.
17. If `run_result.v1.parent_run_id` is present, the child and parent runs must stay within one `brand_id` + `brief_id` lineage.
18. Family artifacts are authoritative at the parent level; repo-local fixtures are mirrors for tests, docs, and adapters.

## Mirroring rule for repo-local fixtures

Allowed repo-local use:

- checked-in fixtures for tests
- example payloads in repo docs
- snapshots used by adapters or CLI smoke tests

Required behavior:

1. Mirror parent-level canonical examples exactly, or generate them from the canonical source.
2. If a repo needs additional local test fixtures, treat them as non-canonical unless promoted back to the parent `protocols/examples/` set.
3. Do not fork field names, ID semantics, or ownership notes inside a repo-local fixture.

## First-slice examples

Canonical example payloads live in:

- `protocols/examples/voice_pack.v1.minimal.json`
- `protocols/examples/voice_pack.v1.rich.json`
- `protocols/examples/brief.v1.minimal.json`
- `protocols/examples/brief.v1.rich.json`
- `protocols/examples/run_result.v1.dry-run.json`
- `protocols/examples/run_result.v1.published.json`
- `protocols/examples/run_result.v1.failed.json`
- `protocols/examples/forecast.v1.completed-minimal.json`
- `protocols/examples/forecast.v1.completed-rich.json`
- `protocols/examples/performance.v1.minimal.json`
- `protocols/examples/performance.v1.rich.json`

These are the examples repo-local fixtures should mirror for the active family handoff slices.
