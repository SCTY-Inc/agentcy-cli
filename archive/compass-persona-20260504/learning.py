"""Persona learning and self-improvement."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from brand_os.core.config import utc_now
from brand_os.core.llm import complete_json
from brand_os.core.storage import data_dir
from brand_os.persona.crud import load_persona, save_persona


def learning_dir() -> Path:
    """Get the learning logs directory."""
    path = data_dir() / "learning"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_learning_log_path(persona_name: str) -> Path:
    """Get the path to a persona's learning log."""
    return learning_dir() / f"{persona_name}.jsonl"


def log_interaction(
    persona_name: str,
    user_input: str,
    response: str,
    feedback: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Log an interaction for learning.

    Args:
        persona_name: Name of the persona
        user_input: User's input
        response: Persona's response
        feedback: Optional feedback on the response
        metadata: Optional additional metadata
    """
    log_path = get_learning_log_path(persona_name)

    entry = {
        "timestamp": utc_now().isoformat(),
        "user_input": user_input,
        "response": response,
        "feedback": feedback,
        "metadata": metadata or {},
    }

    with open(log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_learning_history(persona_name: str, limit: int = 100) -> list[dict[str, Any]]:
    """Load recent learning history for a persona."""
    log_path = get_learning_log_path(persona_name)
    if not log_path.exists():
        return []

    entries = []
    with open(log_path) as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    return entries[-limit:]


CRITIQUE_SYSTEM = """You are an expert at analyzing AI persona performance.
Review the interaction history and provide constructive critique.

Output JSON with:
- strengths: list of things the persona does well
- weaknesses: list of areas for improvement
- patterns: list of observed patterns (good or bad)
- recommendations: list of specific recommendations
"""


def critique_persona(persona_name: str, recent_only: bool = True) -> dict[str, Any]:
    """Generate a critique of persona performance.

    Args:
        persona_name: Name of the persona
        recent_only: If True, only analyze recent interactions

    Returns:
        Critique analysis
    """
    persona = load_persona(persona_name)
    history = load_learning_history(persona_name, limit=20 if recent_only else 100)

    if not history:
        return {
            "strengths": [],
            "weaknesses": ["No interaction history available for analysis"],
            "patterns": [],
            "recommendations": ["Start using the persona to gather data"],
        }

    prompt_parts = [
        "Analyze this persona's performance based on interaction history.",
        "",
        f"## Persona: {persona.get('name')}",
        f"Traits: {', '.join(persona.get('traits', []))}",
        f"Voice: {persona.get('voice', {})}",
        "",
        "## Interaction History",
    ]

    for entry in history:
        prompt_parts.append(f"User: {entry.get('user_input', '')}")
        prompt_parts.append(f"Response: {entry.get('response', '')}")
        if entry.get("feedback"):
            prompt_parts.append(f"Feedback: {entry['feedback']}")
        prompt_parts.append("")

    prompt_parts.append("Provide critique and recommendations.")

    prompt = "\n".join(prompt_parts)

    default = {
        "strengths": [],
        "weaknesses": [],
        "patterns": [],
        "recommendations": [],
    }

    return complete_json(prompt=prompt, system=CRITIQUE_SYSTEM, default=default)


LEARN_SYSTEM = """You are an expert at improving AI personas.
Based on the critique and feedback, suggest updates to the persona definition.

Output JSON with:
- traits_to_add: list of traits to add
- traits_to_remove: list of traits to remove
- voice_updates: object with voice field updates
- new_examples: list of new example interactions to add
- boundary_updates: list of boundaries to add or modify
"""


def suggest_improvements(persona_name: str) -> dict[str, Any]:
    """Suggest improvements based on learning history.

    Args:
        persona_name: Name of the persona

    Returns:
        Suggested improvements
    """
    persona = load_persona(persona_name)
    critique = critique_persona(persona_name)

    prompt = f"""Based on this critique, suggest persona improvements.

## Current Persona
{json.dumps(persona, indent=2)}

## Critique
Strengths: {critique.get('strengths', [])}
Weaknesses: {critique.get('weaknesses', [])}
Patterns: {critique.get('patterns', [])}
Recommendations: {critique.get('recommendations', [])}

Suggest specific updates to improve the persona."""

    default = {
        "traits_to_add": [],
        "traits_to_remove": [],
        "voice_updates": {},
        "new_examples": [],
        "boundary_updates": [],
    }

    return complete_json(prompt=prompt, system=LEARN_SYSTEM, default=default)


def apply_improvements(persona_name: str, improvements: dict[str, Any]) -> dict[str, Any]:
    """Apply suggested improvements to a persona.

    Args:
        persona_name: Name of the persona
        improvements: Improvements from suggest_improvements()

    Returns:
        Updated persona
    """
    persona = load_persona(persona_name)

    # Add new traits
    traits = persona.get("traits", [])
    for trait in improvements.get("traits_to_add", []):
        if trait not in traits:
            traits.append(trait)

    # Remove traits
    for trait in improvements.get("traits_to_remove", []):
        if trait in traits:
            traits.remove(trait)
    persona["traits"] = traits

    # Update voice
    voice = persona.get("voice", {})
    voice.update(improvements.get("voice_updates", {}))
    persona["voice"] = voice

    # Add new examples
    examples = persona.get("examples", [])
    examples.extend(improvements.get("new_examples", []))
    persona["examples"] = examples

    # Update boundaries
    boundaries = persona.get("boundaries", [])
    for boundary in improvements.get("boundary_updates", []):
        if boundary not in boundaries:
            boundaries.append(boundary)
    persona["boundaries"] = boundaries

    # Increment version
    persona["version"] = persona.get("version", 1) + 1

    save_persona(persona_name, persona)
    return persona
