# `run_result.v1 -> performance.v1` thin adapter contract

Status: loop-6 implementation note for the bounded family-owned `agentcy-measure` seam  
Date: 2026-04-12

This note locks the exact adapter contract before any loop-6 code lands.
It is intentionally narrower than a repo bootstrap.
Loop 5 schema, examples, lineage rules, and tests remain the locked protocol baseline unless a concrete seam gap is found.

## Authority and scope

The parent canonical fixture remains the only authority for the upstream publish result:

- `protocols/examples/run_result.v1.published.json`

Loop-6 adapter work must treat that fixture as the sole canonical `run_result.v1` input.
Repo-local mirrors are optional convenience artifacts only.
They must not become a second authority.

This note defines only the thin family-owned seam that:

1. reads canonical published `run_result.v1`
2. accepts a tiny deterministic measurement sidecar
3. emits canonical `performance.v1`

This note does not reopen loop-5 schema design, example redesign, test redesign, `agentcy-measure` bootstrap, live analytics integrations, or broader analytics scope.

## Adapter contract summary

### Inputs

The adapter accepts exactly two logical inputs:

1. canonical upstream artifact: one parent-owned published `run_result.v1`
2. one deterministic sidecar measurement envelope

### Output

The adapter emits one canonical `performance.v1` payload that:

- preserves canonical lineage from `run_result.v1`
- copies publish locators from canonical `run_result.v1` delivery data
- adds only the narrow aggregate measurement fields supplied by the sidecar
- remains valid against `protocols/performance.v1.schema.json`

## Required upstream run-result preconditions

The upstream artifact must already be a valid canonical published `run_result.v1`.
The adapter must reject any upstream input that violates any of these rules:

- `artifact_type` is not `run_result.v1`
- `schema_version` is not `v1`
- `writer` is not `{ "repo": "agentcy-studio", "module": "agentcy-studio" }`
- `workflow` is not `social.post`
- `status` is not `published`
- `delivery.dry_run` is `true`
- no published delivery platforms are present

The adapter is locked to published `social.post` outcomes only.
It must reject dry-run, failed, and non-`social.post` inputs rather than widening the slice.

## Deterministic sidecar envelope

The sidecar exists only to carry aggregate measurements that the upstream publish artifact cannot invent itself.
It must not attempt to replace lineage, rewrite identity, or invent delivery locators.

### Required sidecar fields

- `performance_id`
- `measured_at`
- `observations`

### Optional sidecar fields

- `window`
- `summary.notes`

### Disallowed sidecar authority

The sidecar must not be treated as authoritative for:

- `run_id`
- `brief_id`
- `brand_id`
- `writer`
- `workflow`
- lineage fields copied from canonical `run_result.v1`
- delivery publish locators such as `post_id` and `url`

If those fields are present in a future implementation-specific sidecar transport, they must be ignored or rejected unless they exactly mirror the canonical upstream artifact.
The canonical source remains the parent `run_result.v1` fixture.

## Sidecar shape

A minimal deterministic sidecar shape is:

```json
{
  "performance_id": "givecare.performance.social-fall-checkin.24h.2026-04-13",
  "measured_at": "2026-04-13T17:23:11Z",
  "window": "24h-post-publish",
  "observations": [
    {
      "platform": "linkedin",
      "metrics": {
        "impressions": 1840,
        "clicks": 47
      }
    }
  ],
  "summary": {
    "notes": [
      "Aggregate metrics only."
    ]
  }
}
```

## Observation rules

Each sidecar observation must provide:

- `platform`
- a non-empty aggregate `metrics` object

The `metrics` object must use only fields allowed by `protocols/performance.v1.schema.json`:

- `impressions`
- `reach`
- `engagements`
- `reactions`
- `likes`
- `comments`
- `shares`
- `saves`
- `clicks`
- `video_views`
- `engagement_rate`
- `ctr`

The observation may not use schema-forbidden metric names.
The observation may not supply an empty `metrics` object.
The observation may not carry audience-level data, user-level PII, tokens, secrets, auth material, or warehouse-shaped raw analytics payloads.

## Platform matching and publish-locator rules

Each observation platform must match one published platform in canonical `run_result.v1.delivery.platforms`.

Matching rules:

1. `observation.platform` must equal exactly one canonical published delivery platform.
2. The upstream matched delivery platform must already have at least one publish locator: `post_id` and/or `url`.
3. The emitted `performance.v1` observation must copy available publish locators from the matched canonical delivery platform.
4. The adapter must not invent a `post_id` or `url` from sidecar input when the canonical run result did not provide it.
5. If an observation platform does not match a canonical published platform, the adapter must reject the input.
6. If the canonical matched platform lacks both `post_id` and `url`, the adapter must reject the input as missing publish locator evidence.

In short: publish locators are copied from canonical `run_result.v1` delivery data rather than invented by the adapter or sidecar.

## Output derivation rules

The adapter output must be constructed as follows.

### Copied from canonical `run_result.v1`

- `artifact_type = "performance.v1"`
- `schema_version = "v1"`
- `run_id`
- `brief_id`
- `brand_id`
- `workflow`
- `lineage`
- per-observation `platform`
- per-observation `post_id` when present upstream
- per-observation `url` when present upstream

### Set by the adapter as fixed canonical values

- `writer = { "repo": "agentcy-measure", "module": "agentcy-measure" }`

### Copied from the sidecar

- `performance_id`
- `measured_at`
- `window` when present
- `summary.notes` when present
- per-observation `metrics`

The adapter may also copy canonical upstream publish timing such as `published_at` into observations if a future tiny implementation chooses to do so, but that is not required by this note.

## Locked rejection rules

The adapter must reject, not coerce, these cases:

1. upstream `run_result.v1` is `dry_run`
2. upstream `run_result.v1` is `failed`
3. upstream `run_result.v1.workflow` is not `social.post`
4. a sidecar observation platform does not match a canonical published delivery platform
5. the matched canonical delivery platform is missing both `post_id` and `url`
6. `performance_id` is missing
7. `measured_at` is missing
8. `observations` is missing or empty
9. an observation is missing `platform`
10. an observation is missing `metrics`
11. an observation provides an empty `metrics` object
12. an observation uses metric keys not allowed by the canonical schema
13. sidecar input attempts to invent or override publish locators
14. resulting output would fail `protocols/performance.v1.schema.json`

These rejection rules are part of the seam contract and should be tested directly.

## Minimal implementation posture

Loop 6 remains bounded to the thinnest possible family-owned seam:

- fixture-only harness or tiny adapter only
- canonical parent fixture as sole source authority
- deterministic aggregate sidecar only
- direct success and rejection tests only

Loop-5 schema, examples, and tests stay locked unless a concrete seam gap is found during implementation.
If such a gap appears, it should be documented as a specific protocol defect rather than used to widen scope opportunistically.

## Bottom line

This seam is intentionally small.
Canonical published `run_result.v1` remains authoritative.
The adapter adds only deterministic aggregate measurements and emits canonical `performance.v1`.
It must copy lineage and publish locators from the upstream canonical artifact, never invent them, and reject dry-run, failed, non-`social.post`, missing-locator, and unmatched-platform cases.