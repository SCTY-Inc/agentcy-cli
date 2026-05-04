"""Persona CRUD operations."""
from __future__ import annotations

from typing import Any

from brand_os.persona.storage import (
    delete_persona,
    get_persona_path,
    list_personas,
    load_persona,
    personas_dir,
    save_persona,
)


def get_persona(name: str) -> dict[str, Any]:
    """Get a persona by name (alias for load_persona)."""
    return load_persona(name)



def init_persona(name: str) -> dict[str, Any]:
    """Create an empty persona template."""
    template = {
        "name": name,
        "version": 1,
        "traits": [],
        "voice": {
            "tone": "neutral",
            "vocabulary": "general",
            "patterns": [],
        },
        "boundaries": [],
        "examples": [],
        "context": {},
        "providers": {"default": "gpt-4o-mini"},
    }
    save_persona(name, template)
    return template



def create_persona(
    description: str,
    name: str | None = None,
    from_person: bool = False,
    from_role: bool = False,
) -> dict[str, Any]:
    """Create and persist a persona via the bootstrap flow."""
    from brand_os.persona.bootstrap import bootstrap_persona

    return bootstrap_persona(
        description=description,
        name=name,
        from_person=from_person,
        from_role=from_role,
    )


__all__ = [
    "create_persona",
    "delete_persona",
    "get_persona",
    "get_persona_path",
    "init_persona",
    "list_personas",
    "load_persona",
    "personas_dir",
    "save_persona",
]
