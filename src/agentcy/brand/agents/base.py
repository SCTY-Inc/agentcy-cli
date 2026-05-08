"""Base agent protocol and shared types."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Protocol, runtime_checkable
from uuid import uuid4

from pydantic import BaseModel, Field

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.decision import Decision, DecisionType
from agentcy.brand.signals.schema import Signal


class AgentContext(BaseModel):
    """Context provided to an agent for processing."""

    session_id: str = Field(default_factory=lambda: uuid4().hex[:12])
    brand: str
    signals: list[Signal] = Field(default_factory=list)
    parameters: dict[str, Any] = Field(default_factory=dict)
    history: list[dict[str, Any]] = Field(default_factory=list)


class AgentResult(BaseModel):
    """Result returned by an agent."""

    agent_id: str
    session_id: str
    timestamp: datetime = Field(default_factory=utc_now)

    # Analysis output
    analysis: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""

    # Proposed decisions
    decisions: list[Decision] = Field(default_factory=list)

    # Metadata
    signals_processed: int = 0
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    errors: list[str] = Field(default_factory=list)


@runtime_checkable
class Agent(Protocol):
    """Protocol for specialized agents.

    All agents must implement this interface to participate
    in the orchestration layer.
    """

    @property
    def agent_id(self) -> str:
        """Unique identifier for this agent type."""
        ...

    @property
    def description(self) -> str:
        """Human-readable description of agent capabilities."""
        ...

    @property
    def decision_types(self) -> list[DecisionType]:
        """Types of decisions this agent can propose."""
        ...

    async def process(self, context: AgentContext) -> AgentResult:
        """Process signals and produce analysis + decisions.

        Args:
            context: The agent context with signals and parameters.

        Returns:
            AgentResult with analysis and proposed decisions.
        """
        ...


class BaseAgent(ABC):
    """Abstract base class for agents with common functionality."""

    def __init__(self, model: str = "gemini-2.0-flash"):
        self.model = model
        self._session_id: str | None = None

    @property
    @abstractmethod
    def agent_id(self) -> str:
        """Unique identifier for this agent type."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description of agent capabilities."""
        ...

    @property
    @abstractmethod
    def decision_types(self) -> list[DecisionType]:
        """Types of decisions this agent can propose."""
        ...

    @abstractmethod
    async def _analyze(self, context: AgentContext) -> dict[str, Any]:
        """Perform the core analysis. Subclasses implement this."""
        ...

    @abstractmethod
    async def _propose_decisions(
        self, context: AgentContext, analysis: dict[str, Any]
    ) -> list[Decision]:
        """Generate decision proposals based on analysis."""
        ...

    async def process(self, context: AgentContext) -> AgentResult:
        """Process signals and produce analysis + decisions."""
        self._session_id = context.session_id
        errors: list[str] = []


        try:
            analysis = await self._analyze(context)
        except Exception as e:
            errors.append(f"Analysis failed: {e}")
            analysis = {}


        try:
            decisions = await self._propose_decisions(context, analysis)
        except Exception as e:
            errors.append(f"Decision generation failed: {e}")
            decisions = []


        return AgentResult(
            agent_id=self.agent_id,
            session_id=context.session_id,
            analysis=analysis,
            summary=analysis.get("summary", ""),
            decisions=decisions,
            signals_processed=len(context.signals),
            confidence=analysis.get("confidence", 0.5),
            errors=errors,
        )

    def _create_decision(
        self,
        decision_type: DecisionType,
        brand: str,
        proposal: dict[str, Any],
        rationale: str,
        confidence: float,
        signals_used: list[str] | None = None,
    ) -> Decision:
        """Helper to create a properly attributed decision."""
        return Decision(
            type=decision_type,
            brand=brand,
            agent_id=self.agent_id,
            session_id=self._session_id,
            proposal=proposal,
            rationale=rationale,
            confidence=confidence,
            signals_used=signals_used or [],
        )
