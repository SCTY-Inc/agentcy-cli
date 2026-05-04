"""AI-powered persona generation."""
from __future__ import annotations

from typing import Any

from brand_os.core.llm import complete_json


BOOTSTRAP_SYSTEM = """You are an expert at creating detailed AI persona definitions.
Generate a comprehensive persona based on the user's description.
Output valid JSON with these fields:
- name: string (short identifier)
- description: string (1-2 sentences)
- traits: list of 5-7 personality traits
- voice: object with tone, vocabulary, patterns (list of speech patterns)
- boundaries: list of things this persona won't do
- examples: list of 2-3 example interactions with user/assistant keys
- context: object with relevant background info
"""

PERSON_SYSTEM = """You are an expert at creating AI personas based on real people.
Research the person and create a persona that captures their communication style.
Output valid JSON with these fields:
- name: string (the person's name)
- description: string (who they are)
- traits: list of 5-7 personality traits they exhibit
- voice: object with tone, vocabulary, patterns (speech patterns they use)
- boundaries: list of topics they avoid or stances they take
- examples: list of 2-3 example interactions in their style
- context: object with relevant background info
"""

ROLE_SYSTEM = """You are an expert at creating AI personas for professional roles.
Create a persona for someone in this role with appropriate expertise.
Output valid JSON with these fields:
- name: string (role-based name like "The Advisor")
- description: string (role description)
- traits: list of 5-7 professional traits
- voice: object with tone, vocabulary, patterns (professional patterns)
- boundaries: list of professional boundaries
- examples: list of 2-3 role-appropriate interactions
- context: object with role-specific knowledge areas
"""


def bootstrap_persona(
    description: str,
    name: str | None = None,
    from_person: bool = False,
    from_role: bool = False,
) -> dict[str, Any]:
    """Generate a persona using AI.

    Args:
        description: Free-form description or person/role name
        name: Optional name override for the persona
        from_person: If True, treat description as a real person's name
        from_role: If True, treat description as a professional role

    Returns:
        Generated persona dictionary
    """
    if from_person:
        system = PERSON_SYSTEM
        prompt = f"Create a persona based on: {description}"
    elif from_role:
        system = ROLE_SYSTEM
        prompt = f"Create a persona for the role: {description}"
    else:
        system = BOOTSTRAP_SYSTEM
        prompt = f"Create a persona from this description: {description}"

    default = {
        "name": name or "assistant",
        "description": description,
        "traits": [],
        "voice": {"tone": "neutral", "vocabulary": "general", "patterns": []},
        "boundaries": [],
        "examples": [],
        "context": {},
    }

    result = complete_json(prompt=prompt, system=system, default=default)

    # Override name if provided
    if name:
        result["name"] = name

    # Add version
    result["version"] = 1
    result["providers"] = {"default": "gpt-4o-mini"}

    from brand_os.persona.storage import save_persona

    persona_name = result["name"].lower().replace(" ", "-")
    save_persona(persona_name, result)

    return result
