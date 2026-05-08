"""Self-improving persona learning from interactions.

Based on research from:
- "Self-Improving LLM Agents at Test-Time" (arXiv:2510.07841)
- "Aligning LLMs with Individual Preferences via Interaction" (arXiv:2410.03642)
- "PersonaFuse: Personality Activation-Driven Framework" (arXiv:2509.07370)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from agentcy.persona.llm import DEFAULT_MODEL, complete_json

if TYPE_CHECKING:
    from agentcy.persona.persona import Persona

FEEDBACK_ANALYSIS_PROMPT = """Analyze this conversation to extract learnings for improving the persona.

PERSONA:
{persona}

CONVERSATION:
{conversation}

USER FEEDBACK (if any):
{feedback}

Analyze and return JSON with:
- "effective_patterns": list of response patterns that worked well
- "ineffective_patterns": list of response patterns that didn't work
- "suggested_traits": list of traits to add based on what worked
- "suggested_boundaries": list of boundaries to add based on issues
- "voice_adjustments": object with tone/vocabulary suggestions
- "example_to_add": a good exchange to add to examples (or null)
- "confidence": 0.0-1.0 confidence in these suggestions
"""

SELF_CRITIQUE_PROMPT = """You are a persona optimization expert. Review this persona definition and suggest improvements.

CURRENT PERSONA:
{persona}

INTERACTION HISTORY SUMMARY:
- Total conversations: {total_conversations}
- Average drift score: {avg_drift}
- Common issues: {common_issues}

Suggest specific, actionable improvements to make this persona more consistent and effective.
Return JSON with:
- "trait_changes": list of {"action": "add"|"remove"|"modify", "trait": "...", "reason": "..."}
- "voice_changes": list of {"field": "tone"|"vocabulary"|"patterns", "suggestion": "...", "reason": "..."}
- "boundary_changes": list of {"action": "add"|"remove", "boundary": "...", "reason": "..."}
- "description_rewrite": suggested new description (or null if current is good)
- "priority": "high"|"medium"|"low" - urgency of changes
"""


@dataclass
class InteractionLog:
    """Log of a single interaction for learning."""

    timestamp: str
    messages: list[dict[str, str]]
    feedback: str = ""  # User feedback if provided
    drift_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "timestamp": self.timestamp,
            "messages": self.messages,
            "feedback": self.feedback,
            "drift_score": self.drift_score,
        }

    @classmethod
    def from_dict(cls, data: dict) -> InteractionLog:
        return cls(**data)


@dataclass
class LearningState:
    """Persistent learning state for a persona."""

    persona_name: str
    interactions: list[InteractionLog] = field(default_factory=list)
    learned_patterns: list[str] = field(default_factory=list)
    improvement_history: list[dict] = field(default_factory=list)

    @property
    def log_path(self) -> Path:
        return Path.home() / ".prsna" / "learning" / f"{self.persona_name}.json"

    def save(self) -> None:
        """Persist learning state to disk."""
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("w") as f:
            json.dump(
                {
                    "persona_name": self.persona_name,
                    "interactions": [i.to_dict() for i in self.interactions],
                    "learned_patterns": self.learned_patterns,
                    "improvement_history": self.improvement_history,
                },
                f,
                indent=2,
            )

    @classmethod
    def load(cls, persona_name: str) -> LearningState:
        """Load learning state from disk."""
        state = cls(persona_name=persona_name)
        if not state.log_path.exists():
            return state
        with state.log_path.open() as f:
            data = json.load(f)
        state.learned_patterns = data.get("learned_patterns", [])
        state.improvement_history = data.get("improvement_history", [])
        state.interactions = [
            InteractionLog.from_dict(i) for i in data.get("interactions", [])
        ]
        return state


def log_interaction(
    persona: Persona,
    messages: list[dict[str, str]],
    feedback: str = "",
    drift_score: float = 0.0,
) -> None:
    """Log an interaction for future learning.

    Args:
        persona: The persona used
        messages: The conversation messages
        feedback: Optional user feedback
        drift_score: Optional drift score from monitoring
    """
    state = LearningState.load(persona.name)
    state.interactions.append(
        InteractionLog(
            timestamp=datetime.now(UTC).isoformat(),
            messages=messages,
            feedback=feedback,
            drift_score=drift_score,
        )
    )
    # Keep last 100 interactions
    state.interactions = state.interactions[-100:]
    state.save()


def analyze_interactions(
    persona: Persona,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Analyze logged interactions to extract learnings.

    Args:
        persona: The persona to analyze
        model: LLM model to use

    Returns:
        Dict with suggested improvements
    """
    state = LearningState.load(persona.name)

    if len(state.interactions) < 3:
        return {"error": "Need at least 3 interactions for meaningful analysis"}

    # Format recent interactions
    recent = state.interactions[-10:]
    conversation_text = _format_interactions(recent)

    # Collect feedback
    feedback_text = "\n".join(i.feedback for i in recent if i.feedback) or "No explicit feedback"

    prompt = FEEDBACK_ANALYSIS_PROMPT.format(
        persona=persona.to_prompt(),
        conversation=conversation_text,
        feedback=feedback_text,
    )

    return complete_json(prompt, model=model, default={"error": "Failed to parse LLM response"})


def _format_interactions(interactions: list[InteractionLog]) -> str:
    """Format interactions for analysis prompt."""
    parts = []
    for interaction in interactions:
        for msg in interaction.messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")[:200]
            parts.append(f"{role}: {content}")
        parts.append("---")
    return "\n".join(parts)


def self_critique(
    persona: Persona,
    model: str = "gpt-4o",
) -> dict:
    """Have the persona critique itself and suggest improvements.

    Uses a stronger model for deeper analysis.

    Args:
        persona: The persona to critique
        model: LLM model to use (recommend gpt-4o for quality)

    Returns:
        Dict with prioritized improvement suggestions
    """
    state = LearningState.load(persona.name)
    stats = _compute_drift_stats(state)

    prompt = SELF_CRITIQUE_PROMPT.format(
        persona=persona.to_prompt(),
        total_conversations=stats["total"],
        avg_drift=f"{stats['avg_drift']:.2f}",
        common_issues=stats["common_issues"],
    )

    critique = complete_json(
        prompt, model=model, default={"priority": "low", "error": "Failed to parse"}
    )

    state.improvement_history.append({
        "timestamp": datetime.now(UTC).isoformat(),
        "critique": critique,
        "applied": False,
    })
    state.save()

    return critique


def _compute_drift_stats(state: LearningState) -> dict:
    """Compute drift statistics from learning state."""
    total = len(state.interactions)
    if total == 0:
        return {"total": 0, "avg_drift": 0.0, "common_issues": "insufficient data"}

    avg_drift = sum(i.drift_score for i in state.interactions) / total
    high_drift = [i for i in state.interactions if i.drift_score > 0.3]

    if high_drift:
        high_avg = sum(i.drift_score for i in high_drift) / len(high_drift)
        common_issues = f"{len(high_drift)} high-drift interactions (avg: {high_avg:.0%})"
    else:
        common_issues = "no significant drift detected"

    return {"total": total, "avg_drift": avg_drift, "common_issues": common_issues}


def apply_learnings(
    persona: Persona,
    learnings: dict,
    auto_apply: bool = False,
) -> Persona:
    """Apply learned improvements to a persona.

    Args:
        persona: The persona to improve
        learnings: Output from analyze_interactions or self_critique
        auto_apply: If True, apply all suggestions; if False, only high-confidence ones

    Returns:
        Updated persona (not saved - caller should save)
    """
    confidence_threshold = 0.7 if not auto_apply else 0.5

    # Apply trait changes
    if "trait_changes" in learnings:
        for change in learnings["trait_changes"]:
            if change.get("action") == "add":
                if change["trait"] not in persona.traits:
                    persona.traits.append(change["trait"])
            elif change.get("action") == "remove":
                if change["trait"] in persona.traits:
                    persona.traits.remove(change["trait"])

    # Apply suggested traits from interaction analysis
    if "suggested_traits" in learnings:
        confidence = learnings.get("confidence", 0.5)
        if confidence >= confidence_threshold:
            for trait in learnings["suggested_traits"]:
                if trait not in persona.traits:
                    persona.traits.append(trait)

    # Apply boundary changes
    if "boundary_changes" in learnings:
        for change in learnings["boundary_changes"]:
            if change.get("action") == "add":
                if change["boundary"] not in persona.boundaries:
                    persona.boundaries.append(change["boundary"])
            elif change.get("action") == "remove":
                if change["boundary"] in persona.boundaries:
                    persona.boundaries.remove(change["boundary"])

    # Apply voice adjustments
    if "voice_changes" in learnings:
        for change in learnings["voice_changes"]:
            field = change.get("field")
            suggestion = change.get("suggestion")
            if field == "tone" and suggestion:
                persona.voice.tone = suggestion
            elif field == "vocabulary" and suggestion:
                persona.voice.vocabulary = suggestion
            elif field == "patterns" and suggestion:
                if isinstance(suggestion, list):
                    persona.voice.patterns.extend(suggestion)
                else:
                    persona.voice.patterns.append(suggestion)

    # Add good example if provided
    if "example_to_add" in learnings and learnings["example_to_add"]:
        example = learnings["example_to_add"]
        if isinstance(example, dict) and "user" in example:
            persona.examples.append(example)

    # Rewrite description if suggested
    if "description_rewrite" in learnings and learnings["description_rewrite"]:
        persona.description = learnings["description_rewrite"]

    # Increment version
    persona.version += 1

    return persona
