"""Persona drift detection and monitoring.

Based on research from:
- "Measuring and Controlling Persona Drift in Language Model Dialogs" (arXiv:2402.10962)
- "Persona Vectors" (Anthropic)
- "Examining Identity Drift in Conversations of LLM Agents" (arXiv:2412.00804)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from agentcy.persona.llm import DEFAULT_MODEL, complete_json

if TYPE_CHECKING:
    from agentcy.persona.persona import Persona

DRIFT_DETECTION_PROMPT = """Analyze whether this response is consistent with the persona definition.

PERSONA:
{persona}

RESPONSE:
{response}

Evaluate on these dimensions:
1. TRAIT_ALIGNMENT: Does the response reflect the persona's stated traits?
2. VOICE_CONSISTENCY: Does the tone/vocabulary match the persona's voice?
3. BOUNDARY_RESPECT: Does the response respect the persona's boundaries?
4. FACTUAL_GROUNDING: If the persona has context, is it used correctly?

Return a JSON object with:
- "consistent": true/false
- "drift_score": 0.0-1.0 (0 = fully consistent, 1 = complete drift)
- "issues": list of specific inconsistencies found (empty if consistent)
- "dimension_scores": object with scores for each dimension (0.0-1.0, lower is better)
"""


@dataclass
class DriftScore:
    """Result of drift detection for a single response."""

    consistent: bool
    drift_score: float  # 0 = consistent, 1 = total drift
    issues: list[str] = field(default_factory=list)
    dimension_scores: dict[str, float] = field(default_factory=dict)


@dataclass
class ConversationDrift:
    """Drift analysis for an entire conversation."""

    persona_name: str
    turn_scores: list[DriftScore] = field(default_factory=list)

    @property
    def average_drift(self) -> float:
        """Average drift across all turns."""
        if not self.turn_scores:
            return 0.0
        return sum(s.drift_score for s in self.turn_scores) / len(self.turn_scores)

    @property
    def drift_trend(self) -> str:
        """Detect if drift is increasing over conversation."""
        if len(self.turn_scores) < 3:
            return "insufficient_data"

        first_half = self.turn_scores[:len(self.turn_scores)//2]
        second_half = self.turn_scores[len(self.turn_scores)//2:]

        first_avg = sum(s.drift_score for s in first_half) / len(first_half)
        second_avg = sum(s.drift_score for s in second_half) / len(second_half)

        if second_avg > first_avg + 0.1:
            return "increasing"
        elif second_avg < first_avg - 0.1:
            return "decreasing"
        return "stable"

    @property
    def needs_refresh(self) -> bool:
        """Determine if persona needs to be refreshed in context."""
        return self.average_drift > 0.3 or self.drift_trend == "increasing"


def detect_drift(
    persona: Persona,
    response: str,
    model: str = DEFAULT_MODEL,
) -> DriftScore:
    """Detect if a single response drifts from persona.

    Args:
        persona: The persona definition
        response: The response to check
        model: LLM model to use for evaluation

    Returns:
        DriftScore with consistency assessment
    """
    prompt = DRIFT_DETECTION_PROMPT.format(
        persona=persona.to_prompt(),
        response=response,
    )

    data = complete_json(
        prompt=prompt,
        model=model,
        default={"consistent": True, "drift_score": 0.0},
    )

    return DriftScore(
        consistent=data.get("consistent", True),
        drift_score=data.get("drift_score", 0.0),
        issues=data.get("issues", []),
        dimension_scores=data.get("dimension_scores", {}),
    )


def monitor_conversation(
    persona: Persona,
    messages: list[dict[str, str]],
    model: str = "gpt-4o-mini",
) -> ConversationDrift:
    """Monitor drift across a conversation.

    Args:
        persona: The persona definition
        messages: List of {"role": ..., "content": ...} messages
        model: LLM model to use for evaluation

    Returns:
        ConversationDrift with per-turn analysis
    """
    drift = ConversationDrift(persona_name=persona.name)

    for msg in messages:
        if msg.get("role") == "assistant":
            score = detect_drift(persona, msg["content"], model)
            drift.turn_scores.append(score)

    return drift


def suggest_refresh_prompt(persona: Persona, drift: ConversationDrift) -> str:
    """Generate a prompt to refresh persona in degraded conversation.

    Based on research showing periodic persona reinforcement helps maintain consistency.
    """
    if not drift.needs_refresh:
        return ""

    # Collect most common issues
    all_issues = []
    for score in drift.turn_scores:
        all_issues.extend(score.issues)

    issue_summary = "; ".join(set(all_issues)[:3]) if all_issues else "general drift"

    return f"""[PERSONA REFRESH]
Remember: You are {persona.name}.
{persona.to_prompt()}

Recent responses have drifted from your core persona (issues: {issue_summary}).
Please re-anchor to your defined traits and voice patterns.
[END REFRESH]"""
