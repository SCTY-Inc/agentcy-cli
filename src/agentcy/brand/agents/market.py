"""Market Analyst agent for trend and opportunity detection."""

from __future__ import annotations

from typing import Any

from agentcy.brand.agents.base import AgentContext, BaseAgent
from agentcy.brand.core.decision import Decision, DecisionType
from agentcy.brand.core.llm import acomplete_json

ANALYSIS_SYSTEM = """You are a market analyst for brand intelligence.
Analyze signals for trends, opportunities, and risks.
Be specific and actionable. Output valid JSON only."""

ANALYSIS_PROMPT = """Analyze these signals for brand "{brand}":

{signals_text}

Return JSON with this structure:
{{
  "summary": "2-3 sentence overview",
  "trends": [
    {{"topic": "...", "direction": "up|down|stable", "confidence": 0.0-1.0, "evidence": "..."}}
  ],
  "opportunities": [
    {{"description": "...", "action": "...", "urgency": "low|medium|high"}}
  ],
  "risks": [
    {{"description": "...", "severity": "low|medium|high", "mitigation": "..."}}
  ],
  "sentiment": -1.0 to 1.0,
  "confidence": 0.0-1.0
}}"""


class MarketAnalyst(BaseAgent):
    """Analyzes market signals to identify trends and opportunities.

    Capabilities:
    - Trend detection from news and market signals
    - Competitor movement analysis
    - Opportunity identification
    - Risk assessment

    Proposes:
    - CAMPAIGN_ADJUSTMENT for market positioning
    - SIGNAL_ACTION for trend responses
    """

    @property
    def agent_id(self) -> str:
        return "market-analyst"

    @property
    def description(self) -> str:
        return "Analyzes market signals to identify trends, opportunities, and competitive dynamics"

    @property
    def decision_types(self) -> list[DecisionType]:
        return [DecisionType.CAMPAIGN_ADJUSTMENT, DecisionType.SIGNAL_ACTION]

    async def _analyze(self, context: AgentContext) -> dict[str, Any]:
        """Analyze market signals for trends and opportunities."""
        if not context.signals:
            return {
                "summary": f"No signals to analyze for {context.brand}",
                "trends": [],
                "opportunities": [],
                "risks": [],
                "sentiment": 0.0,
                "confidence": 0.0,
            }

        # Format signals for LLM
        signals_text = "\n\n".join(
            f"[{s.source.value}] {s.title}\n{s.content[:500]}"
            for s in context.signals[:20]  # Limit to avoid token overflow
        )

        prompt = ANALYSIS_PROMPT.format(
            brand=context.brand,
            signals_text=signals_text,
        )

        result = await acomplete_json(
            prompt=prompt,
            system=ANALYSIS_SYSTEM,
            default={
                "summary": "Analysis failed",
                "trends": [],
                "opportunities": [],
                "risks": [],
                "sentiment": 0.0,
                "confidence": 0.0,
            },
        )

        return result

    async def _propose_decisions(
        self, context: AgentContext, analysis: dict[str, Any]
    ) -> list[Decision]:
        """Generate decision proposals based on market analysis."""
        decisions: list[Decision] = []

        # Example: If significant trend detected, propose campaign adjustment
        if analysis.get("trends"):
            for trend in analysis["trends"]:
                decision = self._create_decision(
                    decision_type=DecisionType.CAMPAIGN_ADJUSTMENT,
                    brand=context.brand,
                    proposal={
                        "action": "adjust_messaging",
                        "trend": trend,
                        "recommended_changes": [],
                    },
                    rationale=f"Market trend detected: {trend.get('topic', 'N/A')} ({trend.get('direction', '?')}) - {trend.get('evidence', '')}",
                    confidence=analysis.get("confidence", 0.5),
                    signals_used=[s.id for s in context.signals[:5]],
                )
                decisions.append(decision)

        return decisions
