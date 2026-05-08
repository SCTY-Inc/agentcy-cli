"""Decision logging and audit trail for agent actions."""

from __future__ import annotations

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.storage import data_dir


class DecisionType(str, Enum):
    """Types of decisions agents can propose."""

    CONTENT_PUBLISH = "content_publish"
    CONTENT_SCHEDULE = "content_schedule"
    SIGNAL_ACTION = "signal_action"
    THREAT_RESPONSE = "threat_response"
    COMPETITOR_RESPONSE = "competitor_response"
    BUDGET_ALLOCATION = "budget_allocation"
    CAMPAIGN_ADJUSTMENT = "campaign_adjustment"
    ALERT_ESCALATION = "alert_escalation"


class DecisionStatus(str, Enum):
    """Decision lifecycle status."""

    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTED = "executed"
    FAILED = "failed"
    EXPIRED = "expired"


class Decision(BaseModel):
    """A logged decision from an agent."""

    id: str = Field(default_factory=lambda: uuid4().hex[:12])
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

    # Classification
    type: DecisionType
    brand: str
    agent_id: str | None = None
    session_id: str | None = None

    # Proposal
    proposal: dict[str, Any]
    rationale: str
    confidence: float = Field(ge=0.0, le=1.0)

    # Supporting data
    signals_used: list[str] = Field(default_factory=list)  # Signal IDs
    context: dict[str, Any] = Field(default_factory=dict)

    # Review
    status: DecisionStatus = DecisionStatus.DRAFT
    reviewer: str | None = None
    review_reason: str | None = None
    reviewed_at: datetime | None = None

    # Execution
    executed_at: datetime | None = None
    outcome: dict[str, Any] | None = None
    error: str | None = None


class DecisionLog:
    """File-based decision log with SQLite-like query capabilities.

    Uses JSON lines format for simplicity. Can be upgraded to SQLite
    via aiosqlite when needed.
    """

    def __init__(self, brand: str | None = None):
        self.brand = brand
        self._log_dir = data_dir() / "decisions"
        self._log_dir.mkdir(parents=True, exist_ok=True)

    def _get_log_file(self, brand: str) -> Path:
        return self._log_dir / f"{brand}.jsonl"

    def log(self, decision: Decision) -> Decision:
        """Log a new decision."""
        decision.updated_at = utc_now()
        log_file = self._get_log_file(decision.brand)

        with log_file.open("a") as f:
            f.write(decision.model_dump_json() + "\n")

        return decision

    def update(self, decision: Decision) -> Decision:
        """Update an existing decision by rewriting the log."""
        decision.updated_at = utc_now()
        log_file = self._get_log_file(decision.brand)

        if not log_file.exists():
            return self.log(decision)

        # Read all, update matching, write back
        lines = log_file.read_text().strip().split("\n")
        updated = False
        new_lines = []

        for line in lines:
            if not line:
                continue
            existing = Decision.model_validate_json(line)
            if existing.id == decision.id:
                new_lines.append(decision.model_dump_json())
                updated = True
            else:
                new_lines.append(line)

        if not updated:
            new_lines.append(decision.model_dump_json())

        log_file.write_text("\n".join(new_lines) + "\n")
        return decision

    def get(self, decision_id: str, brand: str | None = None) -> Decision | None:
        """Get a decision by ID."""
        brands = [brand] if brand else self._list_brands()

        for b in brands:
            log_file = self._get_log_file(b)
            if not log_file.exists():
                continue

            for line in log_file.read_text().strip().split("\n"):
                if not line:
                    continue
                decision = Decision.model_validate_json(line)
                if decision.id == decision_id:
                    return decision

        return None

    def list(
        self,
        brand: str | None = None,
        status: DecisionStatus | None = None,
        decision_type: DecisionType | None = None,
        limit: int = 100,
    ) -> list[Decision]:
        """List decisions with optional filters."""
        brands = [brand] if brand else self._list_brands()
        results: list[Decision] = []

        for b in brands:
            log_file = self._get_log_file(b)
            if not log_file.exists():
                continue

            for line in log_file.read_text().strip().split("\n"):
                if not line:
                    continue
                decision = Decision.model_validate_json(line)

                if status and decision.status != status:
                    continue
                if decision_type and decision.type != decision_type:
                    continue

                results.append(decision)

                if len(results) >= limit:
                    break

        # Sort by created_at descending
        results.sort(key=lambda d: d.created_at, reverse=True)
        return results[:limit]

    def _list_brands(self) -> list[str]:
        """List all brands with decision logs."""
        return [f.stem for f in self._log_dir.glob("*.jsonl")]


# Convenience functions
_default_log: DecisionLog | None = None


def get_decision_log() -> DecisionLog:
    """Get the default decision log instance."""
    global _default_log
    if _default_log is None:
        _default_log = DecisionLog()
    return _default_log


def log_decision(decision: Decision) -> Decision:
    """Log a decision using the default log."""
    return get_decision_log().log(decision)


def get_decision(decision_id: str, brand: str | None = None) -> Decision | None:
    """Get a decision by ID."""
    return get_decision_log().get(decision_id, brand)


def list_decisions(
    brand: str | None = None,
    status: DecisionStatus | None = None,
    decision_type: DecisionType | None = None,
    limit: int = 100,
) -> list[Decision]:
    """List decisions with optional filters."""
    return get_decision_log().list(brand, status, decision_type, limit)
