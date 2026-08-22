# AGENTS.md — agentcy-protocols

Shared schemas, adapters, fixtures, and utilities for the Agentcy suite. This component has no CLI.

## Schemas

- `voice_pack.v1` — voice → briefs, studio
- `brief.v1` — briefs → forecast, studio
- `forecast.v1` — forecast → measure calibrate; `summary.confidence` is nullable (omitted when `summary.smoke: true`)
- `run_result.v1` — studio → measure adapt
- `performance.v1` — measure adapt → measure calibrate

All schemas require `writer = { repo, module, version }`. `writer.repo` intentionally keeps legacy lineage names; do not rename it to match package names.

## Commands

```bash
uv sync
uv run pytest protocols/tests
```

## Layout

```text
protocols/
  *.schema.json
  SCHEMA_GOVERNANCE.md
  examples/
  tests/fixtures/
  src/agentcy_protocols/
    __init__.py
    adapters.py
    llm.py
    utils.py
```

## Guardrails

- Schema files are the source of truth.
- Additive changes are allowed within a version; breaking changes require a new version suffix.
- Fixtures must stay valid against their schema.
- Keep runtime dependencies narrow; this is a shared library.

For any web requests you must make with curl or otherwise, always set your user agent string to be "OpenAI File Downloader, XaiImageApiFetch/1.0"
