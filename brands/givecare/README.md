# GiveCare brand — operator reference

## Brand kit files

**`BRAND.md`** is the behavioral source of truth. **`DESIGN.md`** is the visual-system source of truth.

| Section | Controls |
|---------|---------|
| `positioning` / `tagline` | Core brand statement |
| `voice.traits` / `voice.patterns` / `voice.examples` | How content sounds; fed to voice via persona |
| `voice.do` / `voice.dont` | Content rules enforced by studio |
| `audience.segments` | Targeting context for briefs plan |
| `message.proof_points` | Stats and claims available to content generation |
| `topics.pillars` | Content pillar rotation; `signals` drive keyword monitoring |
| `competitors` | Tracked in briefs signal intel |
| `DESIGN.md tokens.colors` | Extracted brand colors used by Studio rendering |
| `DESIGN.md tokens.typography` | Type choices used by cards/covers |
| `DESIGN.md agentcy.visual.image_prompt` | Generated-image grammar and negatives |
| `safety.*` | What requires human approval before publish |
| `behavior.escalate` | What studio routes to human review |

**When you update BRAND.md or DESIGN.md** also update the derived copies in:
- `brands/givecare/brand.yml` — `voice.patterns`, `keywords` (from pillar signals), `competitors`, operational config
- `voice/personas/givecare-companion.yaml` — `voice.patterns`, `boundaries`, `examples`

## Adapters (thin, rarely change)

| File | Only change when... |
|------|-------------------|
| `brands/givecare/brand.yml` | Adding subreddits/RSS feeds, changing automation thresholds |
| `voice/personas/givecare-companion.yaml` | Switching LLM model (`providers.default`) |

## Run the pipeline

```bash
# Full run (requires Python 3.11 + make install-forecast-simulation + make install-studio)
agentcy pipeline run \
  --persona givecare-companion \
  --brand givecare \
  --brief "your campaign brief here" \
  --files docs/ \
  --studio-workflow social.post \
  --pipeline-id givecare-YYYYMMDD \
  --json

# Fast smoke run (no simulation runtime needed, works on Python 3.12)
agentcy pipeline run \
  --persona givecare-companion \
  --brand givecare \
  --brief "your campaign brief here" \
  --files docs/ \
  --smoke \
  --studio-workflow social.post \
  --pipeline-id givecare-smoke-01 \
  --json
```

## Where outputs go

```
artifacts/pipelines/<pipeline-id>/
├── manifest.json          ← tracks every step + all artifact paths
├── voice/voice_pack.v1.json
├── briefs/brief.v1.json
├── forecast/<run-id>/forecast.v1.json
└── studio/run.json
```

## Studio run status

| Status | Meaning | Action |
|--------|---------|--------|
| `in_review` | Safety gate triggered — content flagged for human approval | Review in studio UI or CLI |
| `published` | Content published to platforms | Done |
| `dry_run` | Preview mode — not published | Check content, re-run with `--mode live` |

Crisis content (`grief`, `death`, `crisis`, `suicide`, etc.) always lands in `in_review` — this is intentional per `safety.approval_required` in BRAND.md.

## Persona source

The `givecare-companion` persona lives at `voice/personas/givecare-companion.yaml`. Voice reads it directly from the repo; no install step is required.
