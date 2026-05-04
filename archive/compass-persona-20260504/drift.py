"""Persona drift detection - check response consistency."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from brand_os.core.llm import complete_json
from brand_os.persona.crud import load_persona


class DriftResult(BaseModel):
    """Result of drift detection analysis."""

    is_consistent: bool
    confidence: float
    trait_adherence: dict[str, float]
    voice_match: float
    boundary_violations: list[str]
    suggestions: list[str]


DRIFT_SYSTEM = """You are an expert at analyzing AI persona consistency.
Given a persona definition and a response, analyze whether the response
matches the persona's traits, voice, and boundaries.

Output JSON with:
- is_consistent: boolean (overall consistency)
- confidence: float 0-1 (confidence in assessment)
- trait_adherence: object mapping traits to scores 0-1
- voice_match: float 0-1 (how well response matches voice)
- boundary_violations: list of any boundaries violated
- suggestions: list of suggestions to improve consistency
"""


def detect_drift(
    persona_name: str,
    response: str,
    context: str | None = None,
) -> DriftResult:
    """Detect if a response drifts from persona definition.

    Args:
        persona_name: Name of the persona
        response: The response to analyze
        context: Optional conversation context

    Returns:
        DriftResult with consistency analysis
    """
    persona = load_persona(persona_name)

    prompt_parts = [
        "Analyze this response for persona consistency.",
        "",
        "## Persona Definition",
        f"Name: {persona.get('name')}",
        f"Description: {persona.get('description', '')}",
        f"Traits: {', '.join(persona.get('traits', []))}",
        f"Voice tone: {persona.get('voice', {}).get('tone', 'neutral')}",
        f"Voice patterns: {', '.join(persona.get('voice', {}).get('patterns', []))}",
        f"Boundaries: {', '.join(persona.get('boundaries', []))}",
        "",
    ]

    if context:
        prompt_parts.extend(["## Context", context, ""])

    prompt_parts.extend([
        "## Response to Analyze",
        response,
        "",
        "Analyze consistency and output JSON.",
    ])

    prompt = "\n".join(prompt_parts)

    default = {
        "is_consistent": True,
        "confidence": 0.5,
        "trait_adherence": {},
        "voice_match": 0.5,
        "boundary_violations": [],
        "suggestions": [],
    }

    result = complete_json(prompt=prompt, system=DRIFT_SYSTEM, default=default)
    return DriftResult(**result)


def check_boundaries(persona_name: str, response: str) -> list[str]:
    """Quick check for boundary violations.

    Returns list of violated boundaries, empty if none.
    """
    result = detect_drift(persona_name, response)
    return result.boundary_violations


def get_consistency_score(persona_name: str, response: str) -> float:
    """Get overall consistency score for a response.

    Returns float 0-1 where 1 is perfectly consistent.
    """
    result = detect_drift(persona_name, response)
    if not result.is_consistent:
        return result.confidence * 0.5  # Penalize inconsistency
    return result.confidence
