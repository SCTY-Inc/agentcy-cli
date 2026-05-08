"""Learning and feedback tracking for self-improvement.

Tracks decision outcomes to enable:
1. Policy threshold adjustment (auto-tune confidence requirements)
2. Prompt improvement (identify what analysis patterns work)
3. Signal source quality (which feeds produce actionable intel)

Human-over-the-loop: System logs everything, surfaces patterns,
humans approve policy changes.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.storage import data_dir
from agentcy.brand.core.decision import Decision, DecisionStatus, DecisionType


class Outcome(BaseModel):
    """Tracked outcome for a decision."""

    decision_id: str
    brand: str
    decision_type: DecisionType
    confidence: float

    # What happened
    status: DecisionStatus
    executed_at: datetime | None = None
    reviewed_by: str | None = None

    # Quality signals
    was_approved: bool = False
    was_rejected: bool = False
    was_executed: bool = False
    execution_success: bool = False

    # Feedback (can be added later)
    human_rating: int | None = Field(default=None, ge=1, le=5)
    feedback_notes: str | None = None

    # Timing
    created_at: datetime = Field(default_factory=utc_now)
    time_to_decision_seconds: int | None = None


class LearningMetrics(BaseModel):
    """Aggregated learning metrics."""

    period_start: datetime
    period_end: datetime
    brand: str | None = None

    # Volume
    total_decisions: int = 0
    decisions_by_type: dict[str, int] = Field(default_factory=dict)

    # Approval rates
    approval_rate: float = 0.0
    rejection_rate: float = 0.0
    auto_executed_rate: float = 0.0

    # Confidence calibration
    avg_confidence_approved: float = 0.0
    avg_confidence_rejected: float = 0.0
    confidence_threshold_recommendation: float | None = None

    # Patterns
    common_rejection_reasons: list[str] = Field(default_factory=list)
    high_success_decision_types: list[str] = Field(default_factory=list)
    low_success_decision_types: list[str] = Field(default_factory=list)


class LearningTracker:
    """Track outcomes and compute learning metrics.

    Usage:
        tracker = LearningTracker()

        # Log outcome when decision is resolved
        tracker.log_outcome(decision)

        # Get metrics for tuning
        metrics = tracker.compute_metrics(brand="acme", days=30)

        # Get recommendations
        recs = tracker.get_recommendations(brand="acme")
    """

    def __init__(self):
        self._log_dir = data_dir() / "learning"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_file(self, brand: str) -> Path:
        return self._log_dir / f"{brand}_outcomes.jsonl"

    def log_outcome(self, decision: Decision) -> Outcome:
        """Log outcome for a resolved decision."""
        outcome = Outcome(
            decision_id=decision.id,
            brand=decision.brand,
            decision_type=decision.type,
            confidence=decision.confidence,
            status=decision.status,
            executed_at=decision.executed_at,
            reviewed_by=decision.reviewer,
            was_approved=decision.status in (DecisionStatus.APPROVED, DecisionStatus.EXECUTED),
            was_rejected=decision.status == DecisionStatus.REJECTED,
            was_executed=decision.status == DecisionStatus.EXECUTED,
            execution_success=decision.status == DecisionStatus.EXECUTED and decision.error is None,
        )


        if decision.reviewed_at:
            delta = decision.reviewed_at - decision.created_at
            outcome.time_to_decision_seconds = int(delta.total_seconds())


        log_file = self._get_log_file(decision.brand)
        with log_file.open("a") as f:
            f.write(outcome.model_dump_json() + "\n")

        return outcome

    def get_outcomes(
        self,
        brand: str,
        days: int = 30,
        decision_type: DecisionType | None = None,
    ) -> list[Outcome]:
        """Get outcomes for analysis."""
        log_file = self._get_log_file(brand)
        if not log_file.exists():
            return []

        cutoff = utc_now() - timedelta(days=days)
        outcomes: list[Outcome] = []

        for line in log_file.read_text().strip().split("\n"):
            if not line:
                continue
            outcome = Outcome.model_validate_json(line)

            if outcome.created_at < cutoff:
                continue
            if decision_type and outcome.decision_type != decision_type:
                continue

            outcomes.append(outcome)

        return outcomes

    def compute_metrics(
        self,
        brand: str,
        days: int = 30,
    ) -> LearningMetrics:
        """Compute aggregated metrics for learning."""
        outcomes = self.get_outcomes(brand, days)

        if not outcomes:
            return LearningMetrics(
                period_start=utc_now() - timedelta(days=days),
                period_end=utc_now(),
                brand=brand,
            )

        # Count by type
        by_type: dict[str, int] = defaultdict(int)
        for o in outcomes:
            by_type[o.decision_type.value] += 1

        # Approval/rejection rates
        approved = [o for o in outcomes if o.was_approved]
        rejected = [o for o in outcomes if o.was_rejected]
        auto_executed = [o for o in outcomes if o.reviewed_by == "policy_engine"]

        total = len(outcomes)
        approval_rate = len(approved) / total if total else 0
        rejection_rate = len(rejected) / total if total else 0
        auto_rate = len(auto_executed) / total if total else 0

        # Confidence calibration
        avg_conf_approved = (
            sum(o.confidence for o in approved) / len(approved)
            if approved else 0
        )
        avg_conf_rejected = (
            sum(o.confidence for o in rejected) / len(rejected)
            if rejected else 0
        )

        # Recommend threshold between approved and rejected averages
        threshold_rec = None
        if approved and rejected and avg_conf_approved > avg_conf_rejected:
            threshold_rec = (avg_conf_approved + avg_conf_rejected) / 2

        # Success by type
        type_success: dict[str, tuple[int, int]] = defaultdict(lambda: (0, 0))
        for o in outcomes:
            success, total_t = type_success[o.decision_type.value]
            type_success[o.decision_type.value] = (
                success + (1 if o.execution_success else 0),
                total_t + 1,
            )

        high_success = [t for t, (s, tot) in type_success.items() if tot >= 5 and s/tot > 0.8]
        low_success = [t for t, (s, tot) in type_success.items() if tot >= 5 and s/tot < 0.5]

        return LearningMetrics(
            period_start=min(o.created_at for o in outcomes),
            period_end=max(o.created_at for o in outcomes),
            brand=brand,
            total_decisions=total,
            decisions_by_type=dict(by_type),
            approval_rate=approval_rate,
            rejection_rate=rejection_rate,
            auto_executed_rate=auto_rate,
            avg_confidence_approved=avg_conf_approved,
            avg_confidence_rejected=avg_conf_rejected,
            confidence_threshold_recommendation=threshold_rec,
            high_success_decision_types=high_success,
            low_success_decision_types=low_success,
        )

    def get_recommendations(self, brand: str, days: int = 30) -> list[str]:
        """Generate actionable recommendations from learning data."""
        metrics = self.compute_metrics(brand, days)
        recs: list[str] = []

        if metrics.total_decisions < 10:
            recs.append("Not enough data yet. Need at least 10 decisions for meaningful recommendations.")
            return recs

        # Confidence threshold
        if metrics.confidence_threshold_recommendation:
            current_default = 0.7  # From policy defaults
            rec = metrics.confidence_threshold_recommendation
            if abs(rec - current_default) > 0.1:
                direction = "raise" if rec > current_default else "lower"
                recs.append(
                    f"Consider {direction}ing confidence threshold to {rec:.2f} "
                    f"(approved avg: {metrics.avg_confidence_approved:.2f}, "
                    f"rejected avg: {metrics.avg_confidence_rejected:.2f})"
                )

        # High rejection rate
        if metrics.rejection_rate > 0.4:
            recs.append(
                f"High rejection rate ({metrics.rejection_rate:.0%}). "
                "Review agent prompts or tighten policy constraints."
            )

        # Low auto-execution
        if metrics.auto_executed_rate < 0.3 and metrics.approval_rate > 0.7:
            recs.append(
                f"Low auto-execution ({metrics.auto_executed_rate:.0%}) despite high approval "
                f"({metrics.approval_rate:.0%}). Consider relaxing policy thresholds."
            )

        # Type-specific
        for dt in metrics.low_success_decision_types:
            recs.append(f"Decision type '{dt}' has low success rate. Review or disable.")

        return recs


# Singleton
_tracker: LearningTracker | None = None


def get_learning_tracker() -> LearningTracker:
    global _tracker
    if _tracker is None:
        _tracker = LearningTracker()
    return _tracker


def log_outcome(decision: Decision) -> Outcome:
    """Log outcome using default tracker."""
    return get_learning_tracker().log_outcome(decision)
