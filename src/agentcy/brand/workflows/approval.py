"""Approval workflow state machine for decision review."""

from __future__ import annotations

from typing import Any

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.decision import Decision, DecisionStatus, get_decision, get_decision_log


class ApprovalWorkflow:
    """Decision review lifecycle with persisted transitions."""

    VALID_TRANSITIONS = {
        DecisionStatus.DRAFT: [DecisionStatus.PENDING_REVIEW],
        DecisionStatus.PENDING_REVIEW: [DecisionStatus.APPROVED, DecisionStatus.REJECTED],
        DecisionStatus.APPROVED: [DecisionStatus.EXECUTED, DecisionStatus.FAILED],
        DecisionStatus.EXECUTED: [DecisionStatus.FAILED],
        DecisionStatus.REJECTED: [],
        DecisionStatus.FAILED: [],
    }

    def __init__(self, decision: Decision):
        self.decision = decision

    def _transition(self, new_status: DecisionStatus) -> None:
        valid = self.VALID_TRANSITIONS.get(self.decision.status, [])
        if new_status not in valid:
            raise ValueError(f"Invalid transition: {self.decision.status} -> {new_status}")
        self.decision.status = new_status
        self.decision.updated_at = utc_now()
        get_decision_log().update(self.decision)

    def submit(self) -> None:
        self._transition(DecisionStatus.PENDING_REVIEW)

    def approve(self, reviewer: str = "unknown", reason: str = "") -> None:
        self.decision.reviewer = reviewer
        self.decision.review_reason = reason
        self.decision.reviewed_at = utc_now()
        self._transition(DecisionStatus.APPROVED)

    def reject(self, reviewer: str = "unknown", reason: str = "") -> None:
        self.decision.reviewer = reviewer
        self.decision.review_reason = reason
        self.decision.reviewed_at = utc_now()
        self._transition(DecisionStatus.REJECTED)

    def execute(self, outcome: dict[str, Any] | None = None) -> None:
        self.decision.executed_at = utc_now()
        self.decision.outcome = outcome
        self._transition(DecisionStatus.EXECUTED)

    def fail(self, error: str = "") -> None:
        self.decision.error = error
        self._transition(DecisionStatus.FAILED)



def approve_decision(
    decision_id: str,
    reviewer: str,
    reason: str = "",
    brand: str | None = None,
) -> Decision | None:
    """Approve a pending decision."""
    decision = get_decision(decision_id, brand)
    if not decision:
        return None

    ApprovalWorkflow(decision).approve(reviewer=reviewer, reason=reason)
    return decision



def reject_decision(
    decision_id: str,
    reviewer: str,
    reason: str,
    brand: str | None = None,
) -> Decision | None:
    """Reject a pending decision."""
    decision = get_decision(decision_id, brand)
    if not decision:
        return None

    ApprovalWorkflow(decision).reject(reviewer=reviewer, reason=reason)
    return decision



def submit_for_review(decision: Decision) -> Decision:
    """Submit a draft decision for review."""
    ApprovalWorkflow(decision).submit()
    return decision



def execute_decision(
    decision_id: str,
    outcome: dict[str, Any] | None = None,
    brand: str | None = None,
) -> Decision | None:
    """Mark an approved decision as executed."""
    decision = get_decision(decision_id, brand)
    if not decision:
        return None

    ApprovalWorkflow(decision).execute(outcome=outcome)
    return decision
