# cli-phantom packaged install/help proof for loop 8

Date: 2026-04-12  
Scope: bounded loop-8 verification that the installed `loom` binary works from outside the repo root.

## Result

Verified: a packed local install of `cli-phantom/runtime` works from a temp directory outside `/Users/amadad/projects/cli-phantom`.

The proof was run from a temp root under `/tmp`, using a locally packed tarball and an external install directory. The installed binary path used for verification was:

```bash
./node_modules/.bin/loom
```

This proves packaged local install/help readiness for the current bounded loop-8 target.

It does **not** claim:

- a repo rename from `cli-phantom` to `agentcy-loom`
- a final package rename from `loom-runtime` to `agentcy-loom`
- that `agentcy-loom` is already the installed binary name

The canonical writer contract remains unchanged:

```json
{
  "repo": "cli-phantom",
  "module": "agentcy-loom"
}
```

## Exact commands run

```bash
cd /Users/amadad/projects/cli-phantom/runtime
npm pack --pack-destination /tmp/loom-pack-proof-Z5CAqr/pack --json

cd /tmp/loom-pack-proof-Z5CAqr/install
npm init -y
npm install /tmp/loom-pack-proof-Z5CAqr/pack/loom-runtime-1.0.0.tgz
./node_modules/.bin/loom --help
./node_modules/.bin/loom help --json
```

## External proof locations

```text
PROOF_ROOT=/tmp/loom-pack-proof-Z5CAqr
PACK_DIR=/tmp/loom-pack-proof-Z5CAqr/pack
INSTALL_DIR=/tmp/loom-pack-proof-Z5CAqr/install
TARBALL=loom-runtime-1.0.0.tgz
```

These paths are outside the repo root and were used specifically to avoid source-tree assumptions masquerading as packaged readiness.

## Observed `loom --help` result

```text
Loom Runtime CLI

Usage:
  loom <command> [options]

Commands:
  auto --brand <id> [--workflow social.post] [--topic "..."] [--dry-run]
  brand <init|show|validate> ...
  run <workflow> --brand <id> [--pillar <id>] [--format <id>] [--brief-file <path>] ...
  review <list|show|approve|reject> ...
  publish <run_id> [--platforms twitter,linkedin] [--dry-run]
  inspect <run|artifact> ...
  retry <run_id> [--from <step>]
  lab <card|render> ...
  ops <health|auth check --brand <id>|auth refresh|migrate>

Workflows:
  social.post
  blog.post
  outreach.touch
  respond.reply

Examples:
  loom auto --brand givecare
  loom auto --brand scty --topic "AI adoption gap" --dry-run
  loom ops auth check --brand givecare
  loom run social.post --brand givecare --topic "caregiver benefits gap"
  loom run social.post --brand givecare --pillar care-economy --topic "$470B unpaid care labor"
  loom run social.post --brand givecare --format infographic --topic "caregiver workforce"
  loom run blog.post --brand givecare --pillar policy --topic "paid leave"
  loom run social.post --brand givecare --brief-file ../protocols/examples/brief.v1.rich.json
  loom lab card --brand givecare --type quote --headline "Care is infrastructure"
  loom lab render --brand givecare --figure statement --gravity high --ground cream --platform linkedin --headline "Care is infrastructure" --body "63M provide unpaid care." --image watershed
  loom publish run_123 --platforms twitter,linkedin --dry-run
```

## Observed `loom help --json` result

```json
{
  "status": "ok",
  "command": "help",
  "data": {
    "help": "Loom Runtime CLI\n\nUsage:\n  loom <command> [options]\n\nCommands:\n  auto --brand <id> [--workflow social.post] [--topic \"...\"] [--dry-run]\n  brand <init|show|validate> ...\n  run <workflow> --brand <id> [--pillar <id>] [--format <id>] [--brief-file <path>] ...\n  review <list|show|approve|reject> ...\n  publish <run_id> [--platforms twitter,linkedin] [--dry-run]\n  inspect <run|artifact> ...\n  retry <run_id> [--from <step>]\n  lab <card|render> ...\n  ops <health|auth check --brand <id>|auth refresh|migrate>\n\nWorkflows:\n  social.post\n  blog.post\n  outreach.touch\n  respond.reply\n\nExamples:\n  loom auto --brand givecare\n  loom auto --brand scty --topic \"AI adoption gap\" --dry-run\n  loom ops auth check --brand givecare\n  loom run social.post --brand givecare --topic \"caregiver benefits gap\"\n  loom run social.post --brand givecare --pillar care-economy --topic \"$470B unpaid care labor\"\n  loom run social.post --brand givecare --format infographic --topic \"caregiver workforce\"\n  loom run blog.post --brand givecare --pillar policy --topic \"paid leave\"\n  loom run social.post --brand givecare --brief-file ../protocols/examples/brief.v1.rich.json\n  loom lab card --brand givecare --type quote --headline \"Care is infrastructure\"\n  loom lab render --brand givecare --figure statement --gravity high --ground cream --platform linkedin --headline \"Care is infrastructure\" --body \"63M provide unpaid care.\" --image watershed\n  loom publish run_123 --platforms twitter,linkedin --dry-run"
  }
}
```

## Bounded interpretation

This is enough evidence to say:

- `loom-runtime` currently supports a real packaged local install path
- `loom` currently works as the installed operator-facing CLI alias from outside the repo root
- loop 8 has a bounded packaged-help proof for `cli-phantom`

This is not enough evidence to say:

- the repo is rename-ready across all surfaces
- `agentcy-loom` is already the packaged binary name
- runtime prefixes or writer fields should change now
