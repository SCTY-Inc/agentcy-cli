# GiveCare brand — operator reference

## One file to edit

**`loom/runtime/brands/givecare/BRAND.md`** is the source of truth.

| Section | Controls |
|---------|---------|
| `positioning` / `tagline` | Core brand statement |
| `voice.traits` / `voice.patterns` / `voice.examples` | How content sounds; fed to vox via persona |
| `voice.do` / `voice.dont` | Content rules enforced by loom |
| `audience.segments` | Targeting context for compass plan |
| `message.proof_points` | Stats and claims available to content generation |
| `topics.pillars` | Content pillar rotation; `signals` drive keyword monitoring |
| `competitors` | Tracked in compass signal intel |
| `visual.palette` | Brand colors |
| `safety.*` | What requires human approval before publish |
| `behavior.escalate` | What loom routes to human review |

**When you update BRAND.md** also update the derived copies in:
- `compass/brands/givecare/brand.yml` — `voice.patterns`, `keywords` (from pillar signals), `competitors`, `visual.palette`
- `vox/personas/givecare-companion.yaml` — `voice.patterns`, `boundaries`, `examples`

## Adapters (thin, rarely change)

| File | Only change when... |
|------|-------------------|
| `compass/brands/givecare/brand.yml` | Adding subreddits/RSS feeds, changing automation thresholds |
| `vox/personas/givecare-companion.yaml` | Switching LLM model (`providers.default`) |

## Run the pipeline

```bash
# Full run (requires Python 3.11 + make install-echo-simulation + make install-loom)
agentcy pipeline run \
  --persona givecare-companion \
  --brand givecare \
  --brief "your campaign brief here" \
  --files docs/ \
  --loom-workflow social.post \
  --pipeline-id givecare-YYYYMMDD \
  --json

# Fast smoke run (no simulation runtime needed, works on Python 3.12)
agentcy pipeline run \
  --persona givecare-companion \
  --brand givecare \
  --brief "your campaign brief here" \
  --files docs/ \
  --smoke \
  --loom-workflow social.post \
  --pipeline-id givecare-smoke-01 \
  --json
```

## Where outputs go

```
artifacts/pipelines/<pipeline-id>/
├── manifest.json          ← tracks every step + all artifact paths
├── vox/voice_pack.v1.json
├── compass/brief.v1.json
├── echo/<run-id>/forecast.v1.json
└── loom/run.json
```

## Loom run status

| Status | Meaning | Action |
|--------|---------|--------|
| `in_review` | Safety gate triggered — content flagged for human approval | Review in loom UI or CLI |
| `published` | Content published to platforms | Done |
| `dry_run` | Preview mode — not published | Check content, re-run with `--mode live` |

Crisis content (`grief`, `death`, `crisis`, `suicide`, etc.) always lands in `in_review` — this is intentional per `safety.approval_required` in BRAND.md.

## Persona install

```bash
make install-personas   # syncs vox/personas/*.yaml → ~/.prsna/personas/
```

Run this after editing `vox/personas/givecare-companion.yaml`.
