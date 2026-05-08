"""Autonomous execution loop for 24/7 operation.

This is the main daemon that runs continuously in a container,
processing signals, running agents, and executing decisions
within policy boundaries.

Human-over-the-loop design:
- Humans configure policies and thresholds
- System operates autonomously within those boundaries
- Exceptions escalated, outcomes tracked
"""

from __future__ import annotations

import asyncio
import signal
import sys
from datetime import datetime, timedelta
from typing import Any, Callable, NoReturn

from pydantic import BaseModel, Field

from agentcy.brand.core.config import list_brands, load_brand_config, utc_now
from agentcy.brand.core.decision import (
    Decision,
    DecisionLog,
    DecisionStatus,
    DecisionType,
    get_decision_log,
    list_decisions,
)
from agentcy.brand.core.policy import (
    BrandPolicy,
    PolicyEngine,
    PolicyEvaluation,
    PolicyVerdict,
    get_policy_engine,
)
from agentcy.brand.core.learning import log_outcome, get_learning_tracker


class LoopConfig(BaseModel):
    """Configuration for the autonomous loop."""

    # Timing
    signal_fetch_interval: int = Field(default=300, ge=10)  # seconds
    agent_run_interval: int = Field(default=600, ge=60)  # seconds
    health_check_interval: int = Field(default=60, ge=10)  # seconds

    # Brands to process (empty = all)
    brands: list[str] = Field(default_factory=list)

    # Concurrency
    max_concurrent_brands: int = Field(default=3, ge=1)
    max_concurrent_agents: int = Field(default=2, ge=1)

    # Retry settings
    max_retries: int = Field(default=3, ge=0)
    retry_delay: int = Field(default=30, ge=1)  # seconds

    # Limits
    max_decisions_per_cycle: int = Field(default=50, ge=1)
    max_executions_per_cycle: int = Field(default=10, ge=1)


class LoopState(BaseModel):
    """Current state of the loop."""

    started_at: datetime = Field(default_factory=utc_now)
    last_signal_fetch: datetime | None = None
    last_agent_run: datetime | None = None
    last_health_check: datetime | None = None

    cycles_completed: int = 0
    signals_processed: int = 0
    decisions_made: int = 0
    decisions_executed: int = 0
    decisions_escalated: int = 0
    errors: int = 0

    is_running: bool = False
    is_healthy: bool = True


class LoopEvent(BaseModel):
    """Event emitted by the loop for monitoring."""

    timestamp: datetime = Field(default_factory=utc_now)
    event_type: str
    brand: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class ManualExecutionRequired(RuntimeError):
    """Raised when a decision requires operator action instead of automation."""


class AutonomousLoop:
    """Main autonomous execution loop.

    Runs continuously, processing signals and executing decisions
    within policy boundaries.

    Usage:
        loop = AutonomousLoop()
        await loop.start()

    CLI:
        agentcy-compass loop start
        agentcy-compass loop status
        agentcy-compass loop stop
    """

    def __init__(self, config: LoopConfig | None = None):
        self.config = config or LoopConfig()
        self.state = LoopState()
        self.policy_engine = get_policy_engine()
        self.decision_log = get_decision_log()

        self._shutdown_event = asyncio.Event()
        self._event_handlers: list[Callable[[LoopEvent], None]] = []
        self._last_analysis: dict[str, Any] | None = None

    def on_event(self, handler: Callable[[LoopEvent], None]) -> None:
        """Register an event handler for monitoring."""
        self._event_handlers.append(handler)

    def _emit(self, event_type: str, brand: str | None = None, **details: Any) -> None:
        """Emit a loop event."""
        event = LoopEvent(event_type=event_type, brand=brand, details=details)
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception:
                pass  # Don't let handler errors crash the loop

    async def start(self) -> None:
        """Start the autonomous loop."""
        self.state.is_running = True
        self.state.started_at = utc_now()
        self._emit("loop_started")

        # Set up signal handlers for graceful shutdown
        for sig in (signal.SIGTERM, signal.SIGINT):
            asyncio.get_event_loop().add_signal_handler(
                sig, lambda: asyncio.create_task(self.stop())
            )

        try:
            await self._run_loop()
        except asyncio.CancelledError:
            pass
        finally:
            self.state.is_running = False
            self._emit("loop_stopped")

    async def stop(self) -> None:
        """Signal the loop to stop gracefully."""
        self._emit("loop_stopping")
        self._shutdown_event.set()

    async def _run_loop(self) -> None:
        """Main loop logic."""
        while not self._shutdown_event.is_set():
            cycle_start = utc_now()

            try:
                # Get brands to process
                brands = self._get_active_brands()

                # Run the cycle
                await self._run_cycle(brands)

                self.state.cycles_completed += 1
                self._emit("cycle_completed", cycles=self.state.cycles_completed)

            except Exception as e:
                self.state.errors += 1
                self._emit("cycle_error", error=str(e))

            # Wait for next cycle
            elapsed = (utc_now() - cycle_start).total_seconds()
            wait_time = max(0, self.config.signal_fetch_interval - elapsed)

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=wait_time
                )
                break  # Shutdown requested
            except asyncio.TimeoutError:
                pass  # Continue loop

    def _get_active_brands(self) -> list[str]:
        """Get list of brands to process."""
        if self.config.brands:
            return self.config.brands

        # Get all brands from config
        return list_brands()

    async def _run_cycle(self, brands: list[str]) -> None:
        """Run one processing cycle for all brands."""
        # Process brands with concurrency limit
        semaphore = asyncio.Semaphore(self.config.max_concurrent_brands)

        async def process_with_limit(brand: str) -> None:
            async with semaphore:
                await self._process_brand(brand)

        tasks = [process_with_limit(brand) for brand in brands]
        await asyncio.gather(*tasks, return_exceptions=True)

    async def _process_brand(self, brand: str) -> None:
        """Process signals and decisions for a single brand."""
        self._emit("brand_processing_started", brand=brand)

        try:
            # Load policy
            policy = self.policy_engine.load_policy(brand)
            if not policy.enabled:
                self._emit("brand_skipped", brand=brand, reason="policy_disabled")
                return

            # Fetch new signals
            signals = await self._fetch_signals(brand)
            self.state.signals_processed += len(signals)

            # Run agents if we have signals
            if signals:
                decisions = await self._run_agents(brand, signals, policy)
                self.state.decisions_made += len(decisions)

                # Process decisions through policy
                await self._process_decisions(decisions, policy)

            self._emit("brand_processing_completed", brand=brand)

        except Exception as e:
            self.state.errors += 1
            self._emit("brand_processing_error", brand=brand, error=str(e))

    async def _fetch_signals(self, brand: str) -> list[Any]:
        """Fetch signals for a brand from configured sources."""
        from agentcy.brand.signals.sources.rss import RSSSource, DEFAULT_FEEDS
        from agentcy.brand.signals.sources.reddit import RedditSource, get_subreddits_for_brand

        # Load brand config
        config = load_brand_config(brand) or {}
        keywords = config.get("keywords", [])

        all_signals: list[Any] = []

        # Fetch from RSS
        try:
            custom_feeds = config.get("feeds", [])
            feeds = custom_feeds if custom_feeds else DEFAULT_FEEDS
            rss_source = RSSSource()
            rss_signals = await rss_source.fetch(
                brand=brand,
                feeds=feeds,
                keywords=keywords if keywords else None,
                max_per_feed=10,
            )
            all_signals.extend(rss_signals)
            self._emit("signals_fetched", brand=brand, source="rss", count=len(rss_signals))
        except Exception as e:
            self._emit("signal_source_error", brand=brand, source="rss", error=str(e))

        # Fetch from Reddit
        try:
            subreddits = get_subreddits_for_brand(config)
            if subreddits:
                reddit_source = RedditSource()
                reddit_signals = await reddit_source.fetch(
                    brand=brand,
                    subreddits=subreddits,
                    keywords=keywords if keywords else None,
                    limit_per_sub=15,
                    min_score=10,
                )
                all_signals.extend(reddit_signals)
                self._emit("signals_fetched", brand=brand, source="reddit", count=len(reddit_signals))
        except Exception as e:
            self._emit("signal_source_error", brand=brand, source="reddit", error=str(e))

        self._emit("signals_total", brand=brand, count=len(all_signals))
        return all_signals

    async def _run_agents(
        self,
        brand: str,
        signals: list[Any],
        policy: BrandPolicy,
    ) -> list[Decision]:
        """Run agents on signals to generate decisions."""
        from agentcy.brand.agents.base import AgentContext
        from agentcy.brand.agents.market import MarketAnalyst

        if not signals:
            return []

        # Create context
        context = AgentContext(
            session_id=f"loop-{utc_now().strftime('%Y%m%d-%H%M%S')}",
            brand=brand,
            signals=signals,
        )

        # Run market analyst (add more agents as needed)
        decisions: list[Decision] = []

        try:
            analyst = MarketAnalyst()
            result = await analyst.process(context)
            decisions.extend(result.decisions)

            # Store analysis for later use in execution
            self._last_analysis = result.analysis

            self._emit(
                "agents_completed",
                brand=brand,
                decisions=len(decisions),
                agent="market-analyst",
            )
        except Exception as e:
            self._emit("agent_error", brand=brand, agent="market-analyst", error=str(e))

        return decisions

    async def _process_decisions(
        self,
        decisions: list[Decision],
        policy: BrandPolicy,
    ) -> None:
        """Process decisions through policy and execute/escalate."""
        # Get recent decisions for rate limiting
        recent = list_decisions(
            brand=policy.brand,
            limit=100,
        )

        executed = 0
        escalated = 0

        for decision in decisions[: self.config.max_decisions_per_cycle]:
            evaluation = self.policy_engine.evaluate(decision, policy, recent)

            if evaluation.verdict == PolicyVerdict.ALLOW:
                if executed < self.config.max_executions_per_cycle:
                    if await self._execute_decision(decision, evaluation):
                        executed += 1
                    else:
                        escalated += 1
                else:
                    await self._escalate_decision(decision, evaluation, "execution_rate_limit")
                    escalated += 1

            elif evaluation.verdict == PolicyVerdict.ESCALATE:
                await self._escalate_decision(decision, evaluation)
                escalated += 1

            else:  # DENY
                decision.status = DecisionStatus.REJECTED
                decision.review_reason = "Blocked by policy"
                self.decision_log.update(decision)
                self._emit(
                    "decision_denied",
                    brand=policy.brand,
                    decision_id=decision.id,
                    reasons=evaluation.reasons,
                )

        self.state.decisions_executed += executed
        self.state.decisions_escalated += escalated

    async def _execute_decision(
        self,
        decision: Decision,
        evaluation: PolicyEvaluation,
    ) -> bool:
        """Execute an approved decision.

        Returns True when the decision completed autonomously and False when it
        had to be escalated for operator handling.
        """
        from agentcy.brand.actions.write import WriteAction

        try:
            outcome = await self._execute_by_type(decision)

            decision.status = DecisionStatus.APPROVED
            decision.reviewed_at = utc_now()
            decision.reviewer = "policy_engine"
            decision.review_reason = f"Auto-approved by rule: {evaluation.rule_matched}"

            write_action = WriteAction()
            analysis = getattr(self, '_last_analysis', None)
            write_result = write_action.execute(decision, analysis)
            outcome["written"] = write_result

            decision.status = DecisionStatus.EXECUTED
            decision.executed_at = utc_now()
            decision.outcome = outcome

            self._emit(
                "decision_executed",
                brand=decision.brand,
                decision_id=decision.id,
                decision_type=decision.type.value,
            )
            return True

        except ManualExecutionRequired as exc:
            decision.reviewer = None
            decision.reviewed_at = None
            await self._escalate_decision(decision, evaluation, str(exc))
            return False

        except Exception as exc:
            decision.status = DecisionStatus.FAILED
            decision.error = str(exc)
            self._emit(
                "decision_failed",
                brand=decision.brand,
                decision_id=decision.id,
                error=str(exc),
            )
            return False

        finally:
            self.decision_log.update(decision)
            log_outcome(decision)

    async def _execute_by_type(self, decision: Decision) -> dict[str, Any]:
        """Execute a decision via its registered handler."""
        handlers = {
            DecisionType.CONTENT_PUBLISH: self._execute_content_publish,
            DecisionType.CONTENT_SCHEDULE: self._execute_content_schedule,
            DecisionType.SIGNAL_ACTION: self._execute_signal_action,
            DecisionType.THREAT_RESPONSE: self._execute_threat_response,
            DecisionType.CAMPAIGN_ADJUSTMENT: self._execute_campaign_adjustment,
            DecisionType.COMPETITOR_RESPONSE: self._execute_competitor_response,
        }

        handler = handlers.get(decision.type)
        if not handler:
            self._manual_execution_required(decision)

        return await handler(decision)

    def _manual_execution_required(self, decision: Decision) -> NoReturn:
        raise ManualExecutionRequired(
            f"Autonomous {decision.type.value} execution is not implemented"
        )

    async def _execute_content_publish(self, decision: Decision) -> dict[str, Any]:
        self._manual_execution_required(decision)

    async def _execute_content_schedule(self, decision: Decision) -> dict[str, Any]:
        self._manual_execution_required(decision)

    async def _execute_signal_action(self, decision: Decision) -> dict[str, Any]:
        self._manual_execution_required(decision)

    async def _execute_threat_response(self, decision: Decision) -> dict[str, Any]:
        self._manual_execution_required(decision)

    async def _execute_campaign_adjustment(self, decision: Decision) -> dict[str, Any]:
        self._manual_execution_required(decision)

    async def _execute_competitor_response(self, decision: Decision) -> dict[str, Any]:
        self._manual_execution_required(decision)

    async def _escalate_decision(
        self,
        decision: Decision,
        evaluation: PolicyEvaluation,
        extra_reason: str | None = None,
    ) -> None:
        """Escalate decision for human review."""
        from agentcy.brand.actions.write import WriteAction

        decision.status = DecisionStatus.PENDING_REVIEW
        reasons = evaluation.reasons.copy()
        if extra_reason:
            reasons.append(extra_reason)
        decision.review_reason = "; ".join(reasons)

        # Write to file for human review
        write_action = WriteAction()
        analysis = getattr(self, '_last_analysis', None)
        write_action.execute(decision, analysis)

        self.decision_log.update(decision)

        # Notify based on policy
        await self._send_escalation_notification(decision, evaluation)

        self._emit(
            "decision_escalated",
            brand=decision.brand,
            decision_id=decision.id,
            priority=evaluation.escalation_priority,
            reasons=reasons,
        )

    async def _send_escalation_notification(
        self,
        decision: Decision,
        evaluation: PolicyEvaluation,
    ) -> None:
        """Send notifications for channels that are wired in this runtime."""
        _ = (decision, evaluation)
        policy = self.policy_engine.load_policy(decision.brand)

        for channel in policy.notify_channels:
            if channel == "cli":
                continue


async def run_loop(config: LoopConfig | None = None) -> None:
    """Run the autonomous loop (convenience function)."""
    loop = AutonomousLoop(config)

    # Add console logging handler
    def log_event(event: LoopEvent) -> None:
        timestamp = event.timestamp.strftime("%H:%M:%S")
        brand = f"[{event.brand}]" if event.brand else ""
        print(f"{timestamp} {event.event_type} {brand} {event.details}")

    loop.on_event(log_event)

    await loop.start()


def main() -> None:
    """Entry point for running the loop directly."""
    try:
        asyncio.run(run_loop())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
        sys.exit(0)


if __name__ == "__main__":
    main()
