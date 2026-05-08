"""Threat Assessor agent for risk and threat detection."""

from __future__ import annotations

from typing import Any

from agentcy.brand.agents.base import AgentContext, BaseAgent
from agentcy.brand.core.decision import Decision, DecisionType


class ThreatAssessor(BaseAgent):
    """Assesses threats and risks from signals.

    Capabilities:
    - Reputation threat detection
    - Competitor threat analysis
    - Regulatory/compliance risk assessment
    - Crisis early warning

    Proposes:
    - THREAT_RESPONSE for identified threats
    - ALERT_ESCALATION for critical issues
    """

    @property
    def agent_id(self) -> str:
        return "threat-assessor"

    @property
    def description(self) -> str:
        return "Assesses threats, risks, and potential crises from brand signals"

    @property
    def decision_types(self) -> list[DecisionType]:
        return [DecisionType.THREAT_RESPONSE, DecisionType.ALERT_ESCALATION]

    async def _analyze(self, context: AgentContext) -> dict[str, Any]:
        """Analyze signals for threats and risks."""

        signals = context.signals
        negative_signals = [s for s in signals if (s.sentiment or 0) < -0.3]
        critical_signals = [s for s in signals if s.urgency.value == "critical"]

        threat_level = "low"
        if critical_signals:
            threat_level = "critical"
        elif negative_signals:
            threat_level = "medium"

        return {
            "summary": f"Threat assessment for {context.brand}: {threat_level}",
            "threat_level": threat_level,
            "threats": [],
            "vulnerabilities": [],
            "negative_sentiment_count": len(negative_signals),
            "critical_signal_count": len(critical_signals),
            "recommended_actions": [],
            "confidence": 0.5,
        }

    async def _propose_decisions(
        self, context: AgentContext, analysis: dict[str, Any]
    ) -> list[Decision]:
        """Generate decision proposals based on threat analysis."""
        decisions: list[Decision] = []

        threat_level = analysis.get("threat_level", "low")

        # Propose alert escalation for critical threats
        if threat_level == "critical":
            decision = self._create_decision(
                decision_type=DecisionType.ALERT_ESCALATION,
                brand=context.brand,
                proposal={
                    "action": "escalate_to_leadership",
                    "threat_level": threat_level,
                    "critical_signals": analysis.get("critical_signal_count", 0),
                },
                rationale="Critical threat level detected requiring immediate attention",
                confidence=0.8,
                signals_used=[s.id for s in context.signals[:10]],
            )
            decisions.append(decision)

        # Propose threat response for medium threats
        elif threat_level == "medium":
            decision = self._create_decision(
                decision_type=DecisionType.THREAT_RESPONSE,
                brand=context.brand,
                proposal={
                    "action": "monitor_and_prepare",
                    "threat_level": threat_level,
                    "monitoring_keywords": [],
                },
                rationale="Elevated threat level detected; increased monitoring recommended",
                confidence=0.6,
                signals_used=[s.id for s in context.signals[:5]],
            )
            decisions.append(decision)

        return decisions
