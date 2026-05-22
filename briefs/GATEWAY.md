# brandOS Gateway Architecture

## Overview

The Gateway is the central coordination layer that routes signals to agents, manages sessions, and handles human approval flows. Inspired by clawdbot's hub-and-spoke design.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Signal Sources                          │
│  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐   │
│  │  News   │ │ Social  │ │Financial│ │   SEC   │ │ Patents │   │
│  └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘ └────┬────┘   │
└───────┼──────────┼──────────┼──────────┼──────────┼───────────┘
        │          │          │          │          │
        └──────────┴──────────┴──────────┴──────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Signal Gateway                              │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Signal Router                          │    │
│  │  • Normalize to Signal schema                           │    │
│  │  • Score relevance                                      │    │
│  │  • Route by urgency/type                                │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│           ┌──────────────────┼──────────────────┐               │
│           ▼                  ▼                  ▼               │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐    │
│  │  Standard Queue │ │   High Queue    │ │  Critical Queue │    │
│  │   (batch)       │ │  (near-real)    │ │  (immediate)    │    │
│  └────────┬────────┘ └────────┬────────┘ └────────┬────────┘    │
└───────────┼──────────────────┼──────────────────┼───────────────┘
            │                  │                  │
            └──────────────────┴──────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Session Manager                               │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  • Create agent sessions                                │    │
│  │  • Track active sessions                                │    │
│  │  • Prevent conflicts                                    │    │
│  │  • Manage session lifecycle                             │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Agent Orchestrator                             │
│                                                                  │
│      ┌───────────────┐ ┌───────────────┐ ┌───────────────┐      │
│      │ Market Analyst│ │Threat Assessor│ │Content Producer│      │
│      └───────┬───────┘ └───────┬───────┘ └───────┬───────┘      │
│              │                 │                 │               │
│              └─────────────────┴─────────────────┘               │
│                              │                                   │
│                    ┌─────────┴─────────┐                        │
│                    │  Result Aggregator │                        │
│                    └─────────┬─────────┘                        │
└──────────────────────────────┼──────────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Decision Pipeline                             │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Decision Log                          │    │
│  │  • Log all proposed decisions                           │    │
│  │  • Track rationale + confidence                         │    │
│  │  • Audit trail                                          │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   Approval Router                        │    │
│  │  • Route to human via CLI / Slack / Email               │    │
│  │  • Track approval status                                │    │
│  │  • Handle timeouts                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
│                              │                                   │
│                              ▼                                   │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    Executor                              │    │
│  │  • Execute approved decisions                           │    │
│  │  • Record outcomes                                      │    │
│  │  • Handle failures                                      │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Signal Gateway

Receives signals from all sources, normalizes to common schema, and routes based on urgency.

```python
class SignalGateway:
    async def ingest(self, raw_data: dict, source: SignalSource) -> Signal:
        """Normalize and ingest a signal."""
        signal = self._normalize(raw_data, source)
        signal.relevance_score = await self._score_relevance(signal)
        await self._route(signal)
        return signal

    async def _route(self, signal: Signal) -> None:
        """Route signal to appropriate queue based on urgency."""
        if signal.urgency == Urgency.CRITICAL:
            await self.critical_queue.put(signal)
        elif signal.urgency == Urgency.HIGH:
            await self.high_queue.put(signal)
        else:
            await self.standard_queue.put(signal)
```

### Session Manager

Manages agent sessions to prevent conflicts and track state.

```python
class SessionManager:
    active_sessions: dict[str, AgentSession]

    def create_session(self, agent_id: str, brand: str) -> AgentSession:
        """Create a new agent session."""
        session = AgentSession(
            id=uuid4().hex[:12],
            agent_id=agent_id,
            brand=brand,
            started_at=datetime.utcnow(),
        )
        self.active_sessions[session.id] = session
        return session

    def get_active_for_brand(self, brand: str) -> list[AgentSession]:
        """Get all active sessions for a brand."""
        return [s for s in self.active_sessions.values() if s.brand == brand]
```

### Agent Orchestrator

Coordinates agent execution, handles parallel runs, aggregates results.

```python
class AgentOrchestrator:
    agents: dict[str, Agent]

    async def run_all(self, brand: str, signals: list[Signal]) -> list[AgentResult]:
        """Run all agents in parallel on the same signals."""
        context = AgentContext(brand=brand, signals=signals)

        tasks = [
            agent.process(context)
            for agent in self.agents.values()
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        return [r for r in results if isinstance(r, AgentResult)]
```

### Approval Router

Routes decisions to appropriate human approval channel.

```python
class ApprovalRouter:
    async def request_approval(self, decision: Decision) -> None:
        """Route decision to human for approval."""
        # Determine channel based on urgency and configuration
        if decision.confidence < 0.5:
            # Low confidence -> require explicit review
            await self._notify_slack(decision)
            await self._notify_email(decision)
        else:
            # High confidence -> CLI notification sufficient
            await self._notify_cli(decision)

    async def _notify_slack(self, decision: Decision) -> None:
        """Send Slack notification with approve/reject buttons."""
        # Uses slack-sdk
        ...

    async def _notify_cli(self, decision: Decision) -> None:
        """Log to CLI for review."""
        ...
```

## CLI Integration

```bash
# Gateway status
brandos gateway status

# Process pending signals
brandos gateway process --brand acme

# View queues
brandos gateway queues

# Run full pipeline
brandos gateway run --brand acme --agents all
```

## Configuration

```yaml
# config/gateway.yml
gateway:
  queues:
    standard:
      batch_size: 50
      interval_seconds: 300  # 5 minutes
    high:
      batch_size: 10
      interval_seconds: 60   # 1 minute
    critical:
      batch_size: 1
      interval_seconds: 0    # Immediate

  approval:
    default_channel: cli
    slack_webhook: ${SLACK_WEBHOOK_URL}
    timeout_hours: 24

  agents:
    parallel: true
    max_concurrent: 3
```

## Future Enhancements

### Event Bus Integration

Replace queues with FastStream/Redis Streams for durability:

```python
from faststream import FastStream
from faststream.redis import RedisBroker

broker = RedisBroker("redis://localhost")
app = FastStream(broker)

@broker.subscriber("signals.critical")
async def handle_critical(signal: Signal):
    await orchestrator.run_immediate(signal)
```

### Durable Execution

Wrap gateway operations in Inngest/Temporal for crash resilience:

```python
@inngest.create_function(
    id="process-signals",
    trigger=inngest.TriggerCron(cron="*/5 * * * *")
)
async def process_signals(step):
    signals = await step.run("fetch", fetch_pending_signals)
    results = await step.run("analyze", lambda: orchestrator.run_all(signals))
    await step.run("log", lambda: log_decisions(results))
```
