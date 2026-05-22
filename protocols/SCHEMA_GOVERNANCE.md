# Schema Governance — agentcy-protocols

Canonical schemas live in `protocols/`. Every inter-tool artifact flows through one of these contracts.

## Schemas

| Schema | From → To | File |
|--------|-----------|------|
| `voice_pack.v1` | voice → briefs, studio | `voice_pack.v1.schema.json` |
| `brief.v1` | briefs → forecast, studio | `brief.v1.schema.json` |
| `forecast.v1` | forecast → measure calibrate | `forecast.v1.schema.json` |
| `run_result.v1` | studio → measure adapt | `run_result.v1.schema.json` |
| `performance.v1` | measure adapt → measure calibrate | `performance.v1.schema.json` |

## Versioning

Schemas use `v{n}` suffix. Version bumps are **additive-only** within a major version.

**Allowed without bump:** add optional fields, relax constraints, add enum values.

**Requires bump (v1 → v2):** remove/rename required fields, change field types, tighten constraints, change field semantics.

When bumping: create `brief.v2.schema.json` alongside the old. Both coexist until all writers and readers migrate. Remove old only after full migration.

## Required Fields

All artifacts must include a `writer` block:
```json
{
  "writer": {
    "repo": "<canonical repo name>",
    "module": "<agentcy-* package>",
    "version": "<semver>"
  }
}
```

`writer.repo` keeps legacy names for lineage traceability — do not update to match renamed packages.

## Member-Specific Fields

Members may add fields under a namespaced key:
```json
{ "brief": { ... }, "_compass": { "llm_provider": "gemini" } }
```

Underscore-prefixed keys are ignored by validators and consuming members. Never promote a `_member` field into the canonical schema without a version bump.

## Fixtures

Each schema has a canonical fixture under `protocols/tests/fixtures/`. Fixtures must validate against their schema. When adding a field, update the fixture too.

## Deprecation

1. Mark field deprecated in schema description.
2. Writers stop emitting it (still accept it).
3. After one release cycle, remove from schema and fixtures.
4. Bump version if the field was required.

## Validation

```python
from agentcy_protocols import SCHEMAS
import jsonschema, json

schema = json.loads(SCHEMAS["brief.v1"].read_text())
jsonschema.validate(artifact, schema)
```

CI for all producer members (briefs, forecast, studio, measure) should validate output artifacts.
