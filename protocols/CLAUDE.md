# CLAUDE.md — agentcy-protocols

Shared schemas, adapters, and utilities for the agentcy suite. No CLI — pure library.

## Schemas

Five canonical JSON Schema files define all inter-tool contracts:

| Schema | Producer → Consumer | Key fields |
|--------|---------------------|------------|
| `voice_pack.v1` | vox → compass, loom | persona, voice, tone |
| `brief.v1` | compass → echo, loom | topic, angle, audience, cta |
| `forecast.v1` | echo → pulse calibrate | predictions, confidence, platform_breakdown |
| `run_result.v1` | loom → pulse adapt | posts, platform, metrics, publish_status |
| `performance.v1` | pulse adapt → pulse calibrate | engagement, reach, conversion |

All schemas require a `writer` block: `{ repo, module, version }`. `writer.repo` keeps legacy names — do not update to match renamed packages.

## Package layout

```
protocols/
  brief.v1.schema.json
  forecast.v1.schema.json
  run_result.v1.schema.json
  performance.v1.schema.json
  voice_pack.v1.schema.json
  src/agentcy_protocols/
    __init__.py     SCHEMAS + EXAMPLES path dicts, re-exports
    adapters.py     adapt_run_result_to_performance()
    llm.py          LLMProvider, LLMError
    utils.py        load_json, load_json_optional, write_json
  examples/         One .json per schema (reference artifacts)
  tests/fixtures/   Integration test fixtures per schema version
  SCHEMA_GOVERNANCE.md  Versioning, deprecation, extension rules
```

## Install

```bash
# As workspace dep (all monorepo members)
uv sync  # protocols is auto-resolved via [tool.uv.sources]

# Standalone
pip install -e protocols/
```

## Usage

```python
from agentcy_protocols import SCHEMAS, load_json, adapt_run_result_to_performance

# Validate an artifact
import jsonschema, json
schema = json.loads(SCHEMAS["brief.v1"].read_text())
jsonschema.validate(my_artifact, schema)

# Adapt run_result → performance
performance = adapt_run_result_to_performance(run_result, sidecar)
```

## Governance

See `SCHEMA_GOVERNANCE.md` for versioning rules, deprecation timeline, and member-specific field conventions. The short version: additive changes are fine within a version; breaking changes require a new version suffix.

## Guardrails

- No CLI, no runtime deps beyond stdlib and `pydantic`
- Schema files are the source of truth — code adapters derive from them
- Never remove a schema field without a version bump
- Fixtures in `tests/fixtures/` must stay valid against their schema
