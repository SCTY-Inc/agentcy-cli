# AGENTS.md — agentcy-compass

Brand ops CLI with autonomous execution. Compass owns brand planning and `brief.v1` generation.

## Current Surfaces

- Python distribution: `agentcy-compass`
- Python import root: `brand_os`
- installed CLI: `agentcy-compass`
- dispatcher alias: `agentcy compass ...`
- writer contract: `brief.v1.writer = { repo: "brand-os", module: "agentcy-compass" }`

Preferred stage surfaces are `brand`, `signals`, `intel`, and `plan`. `produce`, `eval`, `publish`, and `monitor` are secondary. Persona commands are deprecated; use `agentcy-vox`.

## Brand-Seeded Research

`plan/stages/research.py` now loads `brand.yml` competitors before calling the LLM. If `brand` is passed, known competitors are injected into the prompt so the LLM enriches them rather than inventing its own list.

`plan/brief_v1.py` now prefers `offer.cta` from `brand.yml` over any LLM-generated CTA that contains bracket placeholders. Add `offer.cta` to `compass/brands/<name>/brand.yml` to lock the CTA across all runs.

## Commands

```bash
uv sync
uv run agentcy-compass --help
BRANDOPS_LLM_PROVIDER=claude-cli CLAUDE_MODEL=sonnet uv run agentcy-compass plan run "..." --brand givecare -f json
uv run pytest
uv run ruff check src/
```

Compatible data-producing commands honor global `--json`; `--json-envelope` wraps successful compatible outputs as `{status, command, data}`.

## Agent Architecture

## Overview

agentcy-compass uses specialized AI agents that process signals and propose decisions. Each agent focuses on a specific domain while sharing a common interface for orchestration.

## Agent Protocol

All agents implement the `Agent` protocol:

```python
class Agent(Protocol):
    @property
    def agent_id(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def decision_types(self) -> list[DecisionType]: ...

    async def process(self, context: AgentContext) -> AgentResult: ...
```

## Data Flow

```
Signals → AgentContext → Agent.process() → AgentResult → Decisions
                                                              ↓
                                                    Human Approval
                                                              ↓
                                                        Execution
```

## Core Agents

### Market Analyst (`market-analyst`)

**Purpose**: Analyze market signals for trends and opportunities.

**Inputs**:
- Financial signals (stock prices, currency)
- Competitor signals (product launches, announcements)
- News signals (industry coverage)

**Outputs**:
- Trend analysis
- Opportunity identification
- Campaign adjustment proposals

**Decision Types**:
- `CAMPAIGN_ADJUSTMENT`
- `SIGNAL_ACTION`

### Threat Assessor (`threat-assessor`)

**Purpose**: Identify risks, threats, and potential crises.

**Inputs**:
- Sentiment signals (negative mentions)
- Competitor signals (competitive threats)
- Regulatory signals (compliance risks)

**Outputs**:
- Threat level assessment
- Vulnerability analysis
- Response recommendations

**Decision Types**:
- `THREAT_RESPONSE`
- `ALERT_ESCALATION`

### Content Producer (`content-producer`) — *Planned*

**Purpose**: Generate brand-aligned content based on analysis.

**Inputs**:
- Market analysis results
- Brand voice configuration
- Platform constraints

**Outputs**:
- Platform-specific content
- Publishing recommendations

**Decision Types**:
- `CONTENT_PUBLISH`
- `CONTENT_SCHEDULE`

> **Status**: Planned. Content production currently handled via `agentcy compass produce` CLI.

## AgentContext

Context provided to agents for processing:

```python
class AgentContext(BaseModel):
    session_id: str          # Unique session for this run
    brand: str               # Target brand
    signals: list[Signal]    # Signals to process
    parameters: dict         # Agent-specific parameters
    history: list[dict]      # Previous analysis results
```

## AgentResult

Result returned by agents:

```python
class AgentResult(BaseModel):
    agent_id: str
    session_id: str
    timestamp: datetime
    analysis: dict           # Agent-specific analysis
    summary: str             # Human-readable summary
    decisions: list[Decision]  # Proposed decisions
    signals_processed: int
    confidence: float
    errors: list[str]
```

## Multi-Agent Coordination

### Parallel Execution

Agents can run in parallel on the same signals:

```
                    ┌─────────────────┐
                    │    Signals      │
                    └────────┬────────┘
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
    ┌───────────────┐ ┌───────────────┐ ┌───────────────┐
    │ Market Analyst│ │Threat Assessor│ │Content Producer│
    └───────┬───────┘ └───────┬───────┘ └───────┬───────┘
            │                 │                 │
            └─────────────────┼─────────────────┘
                              ▼
                    ┌─────────────────┐
                    │   Aggregator    │
                    │  (merge results)│
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │ Human Approval  │
                    └─────────────────┘
```

### Session Isolation

Each agent run gets a unique session ID:

- Decisions attributed to `agent_id + session_id`
- Audit trail tracks which agent proposed what
- No cross-contamination between concurrent runs

### Conflict Resolution

When agents propose conflicting decisions:

1. Higher confidence wins (configurable)
2. More specific decision type wins
3. Human reviewer decides ties

## Running Agents

Agents are orchestrated by the autonomous loop rather than a dedicated CLI. The loop fetches signals, runs agents, and processes decisions according to policy.

```bash
# Run one cycle (test mode)
agentcy compass loop test acme

# Start continuous loop
agentcy compass loop start --brand acme

# View agent-proposed decisions
agentcy compass decision list --brand acme

# Review pending decisions
agentcy compass decision pending
```

### Direct Agent Usage (Programmatic)

```python
from brand_os.agents.market import MarketAnalyst
from brand_os.agents.base import AgentContext

analyst = MarketAnalyst()
context = AgentContext(brand="acme", signals=signals)
result = await analyst.process(context)

print(result.summary)
for decision in result.decisions:
    print(f"{decision.type}: {decision.rationale}")
```

## Implementation Notes

### Creating a New Agent

Extend `BaseAgent` and implement the abstract methods:

```python
from brand_os.agents.base import AgentContext, BaseAgent
from brand_os.core.decision import Decision, DecisionType
from brand_os.core.llm import complete_json

class MyAgent(BaseAgent):
    @property
    def agent_id(self) -> str:
        return "my-agent"

    @property
    def description(self) -> str:
        return "Description of what this agent does"

    @property
    def decision_types(self) -> list[DecisionType]:
        return [DecisionType.SIGNAL_ACTION]

    async def _analyze(self, context: AgentContext) -> dict[str, Any]:
        # Use LLM for analysis
        result = complete_json(
            prompt=f"Analyze: {context.signals}",
            system="You are an analyst...",
            default={"summary": "", "confidence": 0.5},
        )
        return result

    async def _propose_decisions(
        self, context: AgentContext, analysis: dict[str, Any]
    ) -> list[Decision]:
        # Generate decisions based on analysis
        return [
            self._create_decision(
                decision_type=DecisionType.SIGNAL_ACTION,
                brand=context.brand,
                proposal={"action": "..."},
                rationale="...",
                confidence=analysis.get("confidence", 0.5),
            )
        ]
```

### LLM Interface

The `complete_json` function handles JSON extraction from LLM responses:

```python
from brand_os.core.llm import complete_json

analysis = complete_json(
    prompt=f"Analyze these signals: {signals}",
    system="You are a market analyst. Return valid JSON.",
    default={"trends": [], "opportunities": []},
    model="gemini-2.0-flash"  # optional, uses default
)
```

## Future Agents

Planned additions:

- **Content Producer**: Generate brand-aligned content from analysis (in progress)
- **Supply Chain Monitor**: Track vendor/logistics signals
- **Budget Optimizer**: Allocate resources based on performance
- **Compliance Checker**: Monitor regulatory requirements
- **Audience Analyzer**: Track demographic/psychographic shifts
