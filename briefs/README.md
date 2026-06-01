# agentcy-briefs

Briefs is the Agentcy brand-planning runtime. It turns a repo-root brand kit into
`brief.v1` artifacts for Studio, Forecast, and Measure.

## Scope

- Package: `agentcy-briefs`
- Import root: `agentcy_briefs`
- CLI: `agentcy-briefs` or `agentcy briefs ...`
- Owned artifact: `brief.v1`
- Writer pair: `{ "repo": "agentcy-briefs", "module": "agentcy-briefs" }`

Primary surfaces are `brand`, `signals`, `intel`, and `plan`. `produce`,
`eval`, `publish`, and `monitor` are secondary surfaces. Persona authoring lives
in `agentcy-voice`.

## Brand Inputs

Briefs reads brands from the monorepo root:

```text
brands/<brand>/
  BRAND.md
  DESIGN.md
  brand.yml
  assets/
```

`BRAND.md` and `DESIGN.md` carry the durable brand and visual contract.
`brand.yml` carries operational planning fields such as competitors, keywords,
platform limits, and policy thresholds.

## Commands

```bash
uv run agentcy-briefs catalog --json
uv run agentcy-briefs plan run "Launch our new API" --brand givecare --json
uv run agentcy-briefs plan run "Launch our new API" \
  --brand givecare \
  --brief-v1-output /tmp/brief.v1.json \
  -f json
```

Provider overrides use the Briefs-specific env names:

```bash
AGENTCY_BRIEFS_LLM_PROVIDER=claude-cli CLAUDE_MODEL=sonnet \
  uv run agentcy-briefs plan run "Launch memo" --brand givecare -f json
```

Runtime state defaults to `~/.agentcy/briefs`; override it with
`AGENTCY_BRIEFS_DATA_DIR`.
