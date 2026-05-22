# brandOS Implementation Roadmap

This document outlines the path from brandOS's current state (~20% of vision) to a full AI-powered brand operations intelligence system.

## Vision Gap Summary

**Current State**: CLI toolkit for content production, persona management, and basic publishing.

**Target State**: Full brand operations intelligence with market analysis, threat assessment, predictive modeling, multi-signal ingestion, human approval workflows, and automated decision execution.

---

## Architecture Evolution

```
Current                          Target
───────                          ──────
┌─────────────┐                  ┌─────────────────────────────────────┐
│   CLI       │                  │           CLI + API Gateway          │
│   Typer     │                  │         Typer + FastAPI              │
└──────┬──────┘                  └──────────────┬──────────────────────┘
       │                                        │
       ▼                                        ▼
┌─────────────┐                  ┌─────────────────────────────────────┐
│   Core      │                  │         Event Bus (FastStream)       │
│  Functions  │                  │    Redis Streams / NATS / Kafka     │
└──────┬──────┘                  └──────────────┬──────────────────────┘
       │                                        │
       ▼                                        ▼
┌─────────────┐                  ┌─────────────────────────────────────┐
│   LLM       │        ──►       │     Agent Orchestration Layer        │
│   Calls     │                  │   LangGraph / PydanticAI / CrewAI   │
└─────────────┘                  └──────────────┬──────────────────────┘
                                                │
                                 ┌──────────────┼──────────────┐
                                 ▼              ▼              ▼
                          ┌──────────┐  ┌──────────┐  ┌──────────┐
                          │ Market   │  │ Threat   │  │ Content  │
                          │ Analyst  │  │ Assessor │  │ Producer │
                          └──────────┘  └──────────┘  └──────────┘
                                                │
                                                ▼
                          ┌─────────────────────────────────────┐
                          │      Human Approval Layer           │
                          │  HumanLayer / python-statemachine   │
                          └──────────────┬──────────────────────┘
                                         │
                                         ▼
                          ┌─────────────────────────────────────┐
                          │        Durable Execution            │
                          │   Temporal / Inngest / Hatchet      │
                          └─────────────────────────────────────┘
```

---

## Phase 1: Foundation (Weeks 1-3)

**Goal**: Add decision logging, signal normalization, and basic human approval.

### 1.1 Decision Log System
Create audit trail for all automated decisions.

```python
# src/agentcy_briefs/core/decision_log.py
from datetime import datetime
from pydantic import BaseModel
from enum import Enum

class DecisionType(Enum):
    CONTENT_PUBLISH = "content_publish"
    SIGNAL_ACTION = "signal_action"
    THREAT_RESPONSE = "threat_response"
    BUDGET_ALLOCATION = "budget_allocation"

class Decision(BaseModel):
    id: str
    timestamp: datetime
    type: DecisionType
    brand: str
    proposal: dict  # What was proposed
    rationale: str  # LLM reasoning
    confidence: float  # 0-1 score
    status: str  # pending, approved, rejected, executed
    approver: str | None  # Human who approved
    outcome: dict | None  # Result after execution
```

**Storage**: SQLite for MVP → PostgreSQL for production

### 1.2 Signal Normalization Layer
Unified schema for all external data sources.

```python
# src/agentcy_briefs/signals/schema.py
class Signal(BaseModel):
    id: str
    source: str  # "twitter", "sec_edgar", "news", etc.
    timestamp: datetime
    brand: str
    signal_type: str  # "mention", "filing", "competitor_move", etc.
    content: str
    metadata: dict
    relevance_score: float  # 0-1
    sentiment: float | None  # -1 to 1
    urgency: str  # "low", "medium", "high", "critical"
```

### 1.3 Human Approval Integration
Add approval gates to high-stakes actions.

**Recommended**: Start with `python-statemachine` (minimal deps) + Slack webhooks.

```python
# src/agentcy_briefs/workflows/approval.py
from statemachine import StateMachine, State

class ActionApproval(StateMachine):
    draft = State(initial=True)
    pending_review = State()
    approved = State()
    rejected = State()
    executed = State(final=True)

    submit = draft.to(pending_review)
    approve = pending_review.to(approved)
    reject = pending_review.to(rejected)
    execute = approved.to(executed)

    def on_enter_pending_review(self):
        # Log to decision system
        # Send Slack/email notification
        pass
```

### 1.4 CLI Extensions

```bash
# New commands
brandos decision list --brand acme --status pending
brandos decision approve <id> --reason "LGTM"
brandos decision reject <id> --reason "Too aggressive"
brandos decision history --brand acme --days 30
```

---

## Phase 2: Signal Ingestion (Weeks 4-6)

**Goal**: Multi-source data collection with relevance filtering.

### 2.1 Data Source Integrations

| Source | Library | Free Tier | Priority |
|--------|---------|-----------|----------|
| Financial | `yfinance`, Finnhub | Unlimited*/60 req/min | P0 |
| News | NewsAPI, GNews | Dev only/100 req/day | P0 |
| SEC Filings | `edgartools` | Unlimited | P1 |
| Reddit | `praw` | 60 req/min | P1 |
| Patents | USPTO PatentsView | Unlimited | P2 |
| Currency | Frankfurter | Unlimited | P2 |

### 2.2 Signal Pipeline Architecture

```python
# src/agentcy_briefs/signals/pipeline.py
from faststream import FastStream
from faststream.redis import RedisBroker

broker = RedisBroker("redis://localhost")
app = FastStream(broker)

@broker.subscriber("signals.raw")
async def normalize_signal(raw: dict) -> None:
    signal = Signal.model_validate(raw)
    # Enrich with relevance score
    signal.relevance_score = await score_relevance(signal)
    # Route based on urgency
    if signal.urgency == "critical":
        await broker.publish(signal, "signals.critical")
    else:
        await broker.publish(signal, "signals.standard")
```

### 2.3 CLI Extensions

```bash
# Source management
brandos signals sources list
brandos signals sources add finnhub --api-key $KEY
brandos signals sources test reddit

# Real-time monitoring
brandos signals watch --brand acme --sources twitter,news
brandos signals fetch --brand acme --since "2 hours ago"
```

---

## Phase 3: Agent Orchestration (Weeks 7-10)

**Goal**: Specialized AI agents with coordination and human oversight.

### 3.1 Agent Framework Selection

**Recommended**: **PydanticAI** for type safety + **LangGraph** for complex workflows.

```python
# src/agentcy_briefs/agents/market_analyst.py
from pydantic_ai import Agent
from pydantic import BaseModel

class MarketAnalysis(BaseModel):
    trends: list[str]
    opportunities: list[dict]
    threats: list[dict]
    confidence: float
    recommendations: list[str]

market_analyst = Agent(
    'anthropic:claude-sonnet-4-20250514',
    system_prompt="""You are a market analyst for brand intelligence.
    Analyze signals for trends, opportunities, and threats.
    Be specific and actionable in recommendations.""",
    result_type=MarketAnalysis
)
```

### 3.2 Multi-Agent Workflow

```python
# src/agentcy_briefs/agents/workflow.py
from langgraph.graph import StateGraph

class BrandIntelState(TypedDict):
    signals: list[Signal]
    market_analysis: MarketAnalysis | None
    threat_assessment: ThreatAssessment | None
    proposed_actions: list[Action]
    approved_actions: list[Action]

workflow = StateGraph(BrandIntelState)
workflow.add_node("analyze_market", market_analyst_node)
workflow.add_node("assess_threats", threat_assessor_node)
workflow.add_node("propose_actions", action_proposer_node)
workflow.add_node("human_review", human_approval_node)
workflow.add_node("execute", execution_node)

# Parallel analysis
workflow.add_edge(START, ["analyze_market", "assess_threats"])
workflow.add_edge(["analyze_market", "assess_threats"], "propose_actions")
workflow.add_edge("propose_actions", "human_review")
workflow.add_edge("human_review", "execute")
```

### 3.3 CLI Extensions

```bash
# Agent operations
brandos agent run market-analyst --brand acme --signals latest
brandos agent run threat-assessor --brand acme --scope competitors
brandos agent workflow full-intel --brand acme

# Interactive mode
brandos agent chat market-analyst --brand acme
```

---

## Phase 4: Predictive Intelligence (Weeks 11-14)

**Goal**: Forecasting, anomaly detection, and trend analysis.

### 4.1 Forecasting Stack

**Recommended**: `statsforecast` (lightweight) with `prophet` for seasonal data.

```python
# src/agentcy_briefs/predict/forecaster.py
from statsforecast import StatsForecast
from statsforecast.models import AutoARIMA, AutoETS

class BrandForecaster:
    def __init__(self):
        self.sf = StatsForecast(
            models=[AutoARIMA(), AutoETS()],
            freq='D'
        )

    def forecast_metric(self, series: pd.DataFrame, horizon: int = 30):
        self.sf.fit(series)
        return self.sf.predict(h=horizon)
```

### 4.2 Anomaly Detection

```python
# src/agentcy_briefs/predict/anomaly.py
from pyod.models.iforest import IForest
from statsmodels.tsa.seasonal import STL

class AnomalyDetector:
    def detect_statistical(self, series, threshold=3.0):
        """STL decomposition + residual thresholding"""
        stl = STL(series, period=7)
        result = stl.fit()
        residuals = result.resid
        return abs(residuals) > threshold * residuals.std()

    def detect_ml(self, features):
        """Isolation Forest for multivariate anomalies"""
        clf = IForest()
        clf.fit(features)
        return clf.predict(features)
```

### 4.3 Changepoint Detection

```python
# src/agentcy_briefs/predict/changepoint.py
import ruptures as rpt

def detect_changepoints(signal, penalty=10):
    """PELT algorithm for O(n) changepoint detection"""
    algo = rpt.Pelt(model="rbf").fit(signal)
    return algo.predict(pen=penalty)
```

### 4.4 CLI Extensions

```bash
# Forecasting
brandos predict forecast --brand acme --metric engagement --horizon 30
brandos predict anomalies --brand acme --metric sentiment --since "7 days"
brandos predict trends --brand acme --detect-changepoints

# Reports
brandos predict report --brand acme --output pdf
```

---

## Phase 5: Durable Execution (Weeks 15-18)

**Goal**: Crash-resilient workflows that survive failures and restarts.

### 5.1 Framework Selection

**Recommended Progression**:
1. **MVP**: `inngest` (zero infrastructure, fast setup)
2. **Production**: `temporal` (full durability, self-hostable)

### 5.2 Inngest Implementation (MVP)

```python
# src/agentcy_briefs/workflows/durable.py
from inngest import Inngest, Event

inngest = Inngest(app_id="brandos")

@inngest.create_function(
    id="daily-intel-report",
    trigger=inngest.TriggerCron(cron="0 8 * * *")  # 8am daily
)
async def daily_intel_report(step):
    # Each step is durable - survives crashes
    signals = await step.run("fetch-signals", fetch_daily_signals)

    analysis = await step.run("analyze-market",
        lambda: market_analyst.run(signals))

    threats = await step.run("assess-threats",
        lambda: threat_assessor.run(signals))

    # Human approval gate
    approval = await step.wait_for_event(
        "brandos/intel-approved",
        timeout="24h"
    )

    if approval.data["approved"]:
        await step.run("send-report", lambda: send_report(analysis, threats))
```

### 5.3 CLI Extensions

```bash
# Workflow management
brandos workflow list
brandos workflow run daily-intel --brand acme
brandos workflow status <run-id>
brandos workflow replay <run-id> --from-step analyze-market
```

---

## Dependency Evolution

### Current (pyproject.toml)
```toml
[project]
dependencies = [
    "typer>=0.9.0",
    "rich>=13.0.0",
    "pydantic>=2.0.0",
    "httpx>=0.24.0",
    "pyyaml>=6.0",
]
```

### Phase 1 Additions
```toml
[project.optional-dependencies]
core = [
    "python-statemachine>=2.0",
    "aiosqlite>=0.19.0",
    "slack-sdk>=3.20.0",
]
```

### Phase 2 Additions
```toml
signals = [
    "faststream[redis]>=0.5.0",
    "praw>=7.7.0",
    "yfinance>=0.2.0",
    "edgartools>=0.30.0",
]
```

### Phase 3 Additions
```toml
agents = [
    "pydantic-ai>=0.1.0",
    "langgraph>=0.1.0",
]
```

### Phase 4 Additions
```toml
predict = [
    "statsforecast>=1.7.0",
    "pyod>=1.1.0",
    "ruptures>=1.1.8",
]
```

### Phase 5 Additions
```toml
durable = [
    "inngest>=0.4.0",
    # Later: temporalio>=1.4.0
]
```

---

## Implementation Priority

| Priority | Feature | Complexity | Impact |
|----------|---------|------------|--------|
| P0 | Decision log + audit trail | Low | High |
| P0 | Signal normalization schema | Low | High |
| P0 | Basic human approval (CLI) | Low | High |
| P1 | Slack approval integration | Medium | High |
| P1 | Financial data ingestion | Low | Medium |
| P1 | News aggregation | Low | Medium |
| P2 | Multi-agent workflow | High | High |
| P2 | Anomaly detection | Medium | Medium |
| P2 | Forecasting | Medium | Medium |
| P3 | Durable execution | High | High |
| P3 | Full changepoint analysis | Medium | Low |

---

## Success Metrics

### Phase 1
- [ ] All actions logged with decision rationale
- [ ] 100% of high-stakes actions require approval
- [ ] Approval latency < 1 hour (Slack notification)

### Phase 2
- [ ] 5+ signal sources integrated
- [ ] Signal relevance scoring accuracy > 80%
- [ ] Real-time monitoring with < 5 min latency

### Phase 3
- [ ] Specialized agents for market/threat/content
- [ ] Human approval gate for all proposed actions
- [ ] Agent coordination with parallel execution

### Phase 4
- [ ] Forecasting accuracy (MAPE) < 15%
- [ ] Anomaly detection precision > 90%
- [ ] Trend changepoint detection within 24h

### Phase 5
- [ ] Zero data loss on process crashes
- [ ] Workflow replay capability
- [ ] 99.9% execution reliability

---

## Research Sources

### Event-Driven Architecture
- [Inngest Python SDK](https://github.com/inngest/inngest-py)
- [Hatchet Workflow Engine](https://github.com/hatchet-dev/hatchet)
- [FastStream](https://github.com/ag2ai/faststream)
- [Taskiq](https://github.com/taskiq-python/taskiq)
- [Temporal Python SDK](https://github.com/temporalio/sdk-python)

### Multi-Agent Orchestration
- [PydanticAI](https://ai.pydantic.dev/)
- [LangGraph](https://www.langchain.com/langgraph)
- [CrewAI](https://github.com/crewAIInc/crewAI)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-python/)

### Data Sources
- [Finnhub Financial API](https://finnhub.io/)
- [SEC EDGAR Tools](https://github.com/dgunning/edgartools)
- [USPTO PatentsView](https://patentsview.org/apis/purpose)
- [FRED Economic Data](https://fred.stlouisfed.org/)
- [NewsAPI](https://newsapi.org/)

### Human-in-the-Loop
- [HumanLayer](https://pypi.org/project/humanlayer/)
- [python-statemachine](https://github.com/fgmacedo/python-statemachine)
- [Prefect Interactive Workflows](https://docs.prefect.io/v3/advanced/interactive)

### Predictive Modeling
- [StatsForecast](https://github.com/Nixtla/statsforecast)
- [Prophet](https://facebook.github.io/prophet/)
- [PyOD](https://github.com/yzhao062/pyod)
- [Ruptures](https://github.com/deepcharles/ruptures)
- [Darts](https://github.com/unit8co/darts)
