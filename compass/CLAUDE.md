# agentcy-compass Development Guidelines

## Project Overview

Brand ops CLI with autonomous execution. Signals, competitive intel, content production, evaluation, and publishing. Member of the agentcy monorepo.

## Current surfaces (monorepo)

- Python distribution: `agentcy-compass`
- Python import root: `brand_os` (unchanged until explicit refactor)
- installed CLI: `agentcy-compass`
- dispatcher alias: `agentcy compass ...`
- writer contract: `brief.v1.writer = { repo: "brand-os", module: "agentcy-compass" }`

The package and CLI are Agentcy-branded, but canonical protocol lineage still keeps the historical `writer.repo` value for compatibility.

Boundary note:
- canonical ownership: `brief.v1`
- preferred stage surfaces: `brand`, `signals`, `intel`, `plan`
- secondary surfaces: `produce`, `eval`, `publish`, `monitor`
- deprecated persona surface: prefer `agentcy-vox`
- use `agentcy-compass catalog --json` for the machine-readable boundary summary

JSON note: compatible data-producing commands now honor a global `--json` flag in addition to legacy `-f json` / `--format json` forms. `--json-envelope` further wraps successful compatible outputs in a normalized `{status, command, data}` envelope. Interactive or richly formatted legacy surfaces may still prefer explicit `--format` values.

**Architecture**: Human-over-the-loop - humans set policies and thresholds, system operates autonomously within those boundaries, exceptions escalated.

## Project Structure

```
src/brand_os/
├── cli.py              # Main CLI entry (Typer)
├── cli_utils.py        # Output formatting helpers
├── loop.py             # Autonomous execution daemon
├── loop_cli.py         # Loop/decision/policy/learn CLI commands
├── core/               # Shared utilities
│   ├── brands.py       # Brand config loading
│   ├── config.py       # App configuration
│   ├── decision.py     # Decision logging + audit trail
│   ├── policy.py       # Policy engine + guardrails
│   ├── learning.py     # Outcome tracking + self-improvement
│   ├── llm.py          # LLM interface (Gemini, Anthropic, Claude CLI)
│   ├── signals.py      # Signal utilities
│   └── storage.py      # Storage paths
├── signals/            # Signal ingestion pipeline
│   ├── schema.py       # Unified Signal model
│   ├── cli.py          # Signals CLI commands
│   ├── relevance.py    # Relevance scoring
│   ├── history.py      # Signal history storage
│   ├── providers/      # Legacy signal providers
│   │   └── google_news.py
│   └── sources/        # Loop data sources
│       ├── rss.py      # RSS/Atom feed fetcher
│       ├── reddit.py   # Reddit signal source
│       └── reddit_discover.py  # Subreddit discovery
├── actions/            # Execution targets
│   ├── write.py        # File output (audit trail)
│   └── notify.py       # Slack/email notifications
├── workflows/          # Approval workflows
│   └── approval.py     # Central decision review state machine
├── agents/             # Specialized AI agents
│   ├── base.py         # Base Agent protocol
│   ├── market.py       # Market analyst (LLM-powered)
│   └── threat.py       # Threat assessor
│   # persona/ archived to archive/compass-persona-20260504/ — use agentcy-vox
├── plan/               # Brief stages + canonical brief_v1 emission
│   ├── brief_v1.py     # brief.v1 builder / writer
│   └── stages/
│       └── normalize.py # Stage-output coercion before Pydantic validation
├── intel/              # Competitive intelligence
├── produce/            # Content production
├── eval/               # Content evaluation
├── publish/            # Social publishing
├── monitor/            # Reporting + analysis helpers
└── server/             # API surface + explicit MCP stub

brands/                 # Brand configurations
├── _template/          # Default template
└── <brand>/
    ├── brand.yml       # Core config + policy
    ├── rubric.yml      # Evaluation criteria
    ├── references/     # Detailed docs (loaded as needed)
    └── assets/         # Logos, templates
```

## Build & Test Commands

```bash
# Install dependencies
uv sync                      # Core only
uv sync --all-extras         # Everything
uv sync --extra workflows    # Phase 1 features

# Development
uv run agentcy-compass --help        # Run CLI
BRANDOPS_LLM_PROVIDER=claude-cli CLAUDE_MODEL=sonnet uv run agentcy-compass plan run "..." --brand givecare -f json
uv run pytest                # Run tests
uv run ruff check src/       # Lint
uv run ruff format src/      # Format
```

## Coding Conventions

- **Language**: Python 3.11+, strict typing, Pydantic models
- **CLI**: Typer with Rich for output formatting
- **Async**: Use async/await for I/O operations
- **Files**: Keep under 500 LOC; split when larger
- **Comments**: Brief comments for non-obvious logic only

## Decision Logging

All agent-proposed actions MUST be logged before execution:

```python
from brand_os.core.decision import Decision, DecisionType, log_decision

decision = Decision(
    type=DecisionType.CONTENT_PUBLISH,
    brand="acme",
    proposal={"content": "...", "platform": "twitter"},
    rationale="High engagement predicted based on competitor analysis",
    confidence=0.85,
)
await log_decision(decision)
```

High-stakes actions require human approval via the approval workflow.

## Multi-Agent Safety

When multiple agents run concurrently:

- Each agent gets a unique session ID
- Decisions logged with agent attribution
- Never modify another agent's pending decisions
- Use `git add <specific-files>` not `git add .`
- Scope commits to own work only

## Signal Sources

The loop fetches signals from multiple sources:

| Source | File | API Key Required |
|--------|------|------------------|
| RSS/Atom feeds | `signals/sources/rss.py` | No |
| Reddit | `signals/sources/reddit.py` | No |
| Subreddit discovery | `signals/sources/reddit_discover.py` | No (LLM optional) |

Configure sources in `brand.yml`:

```yaml
keywords: [AI, automation]      # Filter signals
feeds: []                       # Custom RSS (uses defaults if empty)
subreddits: []                  # Custom subreddits (auto-discovered if empty)
industry: "B2B SaaS"            # For subreddit discovery
target_audience: "CTOs"         # For subreddit discovery
```

```bash
# Discover subreddits for a brand
agentcy-compass signals discover-subreddits --brand acme
agentcy-compass signals discover-subreddits --industry "B2B SaaS" --query "automation"
```

## Signal Processing

All external data normalized to Signal schema before processing:

```python
from brand_os.signals.schema import Signal, SignalSource, SignalType

signal = Signal(
    source=SignalSource.NEWS,
    signal_type=SignalType.NEWS,
    brand="acme",
    title="...",
    content="...",
    relevance_score=0.8,
    urgency=Urgency.MEDIUM,
)
```

## Autonomous Loop

The system runs 24/7 in a container, processing signals and executing decisions within policy boundaries.

```bash
# Start the loop
agentcy-compass loop start                          # All brands
agentcy-compass loop start --brand acme             # Specific brand
agentcy-compass loop test acme                      # Test single cycle

# Docker deployment
docker compose up -d                        # Start container
docker compose logs -f loop                 # View logs
```

## Policy Engine

Policies define what the system can do autonomously vs. what requires human intervention.

```python
from brand_os.core.policy import evaluate_decision, PolicyVerdict

evaluation = evaluate_decision(decision)

if evaluation.verdict == PolicyVerdict.ALLOW:
    # Execute autonomously
elif evaluation.verdict == PolicyVerdict.ESCALATE:
    # Queue for human review
else:  # DENY
    # Blocked by policy
```

Policy configuration per brand in `brand.yml`:

```yaml
policy:
  enabled: true
  default_verdict: escalate
  global_min_confidence: 0.7
  always_allow: [signal_action]
  always_escalate: [budget_allocation]
  rules:
    - name: content-auto-publish
      decision_types: [content_publish]
      min_confidence: 0.8
      max_per_hour: 5
```

```bash
# Policy CLI commands
agentcy-compass policy show acme
agentcy-compass policy test acme --type content_publish --confidence 0.85
agentcy-compass policy templates
```

## Decision Management

All agent-proposed actions are logged and evaluated against policy before execution.

```bash
# View decisions
agentcy-compass decision list
agentcy-compass decision list --brand acme --status pending_review
agentcy-compass decision pending                    # Quick view of items needing review

# Human review (for escalated decisions)
agentcy-compass decision approve <id> --reason "LGTM"
agentcy-compass decision reject <id> --reason "Too risky"
```

## Learning & Self-Improvement

The system tracks decision outcomes to improve over time:

```python
from brand_os.core.learning import log_outcome, get_learning_tracker

# Automatically logged when decisions are executed/rejected
log_outcome(decision)

# Get metrics
tracker = get_learning_tracker()
metrics = tracker.compute_metrics("acme", days=30)
recommendations = tracker.get_recommendations("acme")
```

```bash
# CLI commands
agentcy-compass learn metrics acme --days 30
agentcy-compass learn recommendations acme
```

Metrics tracked:
- Approval/rejection rates by decision type
- Confidence calibration (approved vs rejected avg)
- Auto-execution rate
- Success patterns by decision type

## Guardrails

- Never publish without human approval for new brands
- Never commit API keys or credentials
- Never use `rm`; use `trash` instead
- Test coverage required for core modules
- Run `ruff check && ruff format` before commits
- `brief.v1` writer: `repo = "brand-os"`, `module = "agentcy-compass"`
- Prefer docs/proof-note corrections over CLI/code churn for loop-10 naming work
- Do not imply rename-readiness from `writer.module` alone; package/import/CLI/runtime surfaces are still separate blockers
- Treat `persona`, `produce`, `eval`, `publish`, `queue`, `monitor`, `server`, and residual `cli-agency` lineage as boundary blockers, not cosmetic naming issues
- Unsupported autonomous actions must escalate via `ManualExecutionRequired`; do not restore fake-success placeholders.
- Optional surfaces such as video generation, the Reve provider, MCP server entrypoint, and loop background mode are explicit unsupported paths in this build.

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `GOOGLE_API_KEY` | Gemini API provider |
| `ANTHROPIC_API_KEY` | Anthropic API provider |
| `BRANDOPS_LLM_PROVIDER` | Preferred planning provider (`gemini`, `anthropic`, `claude-cli`, `mock`) |
| `BRANDOPS_LLM_MODEL` | Compass model override when the provider supports model selection |
| `CLAUDE_MODEL` | Claude CLI model alias for local operator runs |
| `OPENAI_API_KEY` | OpenAI/LiteLLM |
| `SLACK_WEBHOOK_URL` | Approval notifications |

## Testing

```bash
uv run pytest                        # All tests
uv run pytest tests/core/            # Core module only
uv run pytest -k "decision"          # Pattern match
uv run pytest --cov=brand_os         # With coverage
```
