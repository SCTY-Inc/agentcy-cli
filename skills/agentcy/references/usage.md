# Agentcy Usage

## Setup

```bash
uv sync --group dev
cd studio && pnpm install
make install-echo-simulation
```

Full Forecast simulation uses the isolated Python 3.11 env from `make install-echo-simulation`. Use `--smoke` for fast local pipeline checks on Python 3.12.

## Discovery

```bash
uv run agentcy catalog --json
uv run agentcy doctor --json
uv run agentcy pipeline run --help
uv run agentcy studio help --json
uv run agentcy studio brand validate <brand> --json
```

## Preview Pipeline

```bash
uv run agentcy pipeline run \
  --pipeline-id givecare-launch-01 \
  --persona scientist \
  --brand givecare \
  --brief "Before fall gets busy, make caregiving feel lighter" \
  --files docs/launch-memo.md \
  --smoke \
  --persona-eval \
  --studio-workflow social.post \
  --mode preview \
  --output-dir artifacts/pipelines \
  --json
```

The pipeline writes a module-first bundle:

```text
artifacts/pipelines/<pipeline_id>/
  voice/
  briefs/
  forecast/
  studio/
  measure/
  reports/
  manifest.json
```

## Direct Stage Commands

```bash
uv run agentcy-voice --json export scientist --to voice-pack.v1
uv run agentcy-briefs plan run "Launch brief" --brand givecare -f json
uv run agentcy-forecast run --files docs/memo.md --requirement "Predict reaction" --smoke --json
uv run agentcy studio run social.post --brand givecare --topic "caregiver benefits gap" --json
uv run agentcy-measure --json study --pipeline-manifest artifacts/pipelines/<pipeline_id>/manifest.json
```
