"""Export personas to various formats."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from agentcy.persona.persona import Persona


def _get_response(ex: dict) -> str:
    """Get assistant response from example dict."""
    return ex.get("assistant", ex.get("response", ""))


def export_prompt(persona: Persona) -> str:
    """Export as plain system prompt."""
    return persona.to_prompt()


def export_eliza(persona: Persona) -> str:
    """Export as Eliza character.json format."""
    character = {
        "name": persona.name,
        "description": persona.description,
        "personality": persona.traits,
        "system": persona.to_prompt(),
        "bio": [persona.description],
        "lore": persona.boundaries,
        "messageExamples": [
            [{"user": ex["user"], "content": {"text": _get_response(ex)}}]
            for ex in persona.examples
        ],
        "style": {
            "all": persona.voice.patterns,
            "chat": [],
            "post": [],
        },
    }
    return json.dumps(character, indent=2)


def export_v2(persona: Persona) -> str:
    """Export as Character Card V2 format."""
    card = {
        "spec": "chara_card_v2",
        "spec_version": "2.0",
        "data": {
            "name": persona.name,
            "description": persona.description,
            "personality": ", ".join(persona.traits),
            "scenario": "",
            "first_mes": "",
            "mes_example": "\n".join(
                f"<START>\nUser: {ex['user']}\n{persona.name}: {_get_response(ex)}"
                for ex in persona.examples
            ),
            "system_prompt": persona.to_prompt(),
            "post_history_instructions": "",
            "creator_notes": f"Exported from agentcy.persona v{persona.version}",
            "tags": persona.traits[:5],
        },
    }
    return json.dumps(card, indent=2)


def export_ollama(persona: Persona) -> str:
    """Export as Ollama Modelfile."""
    lines = [
        "# Modelfile for " + persona.name,
        "FROM llama3.2",
        "",
        "PARAMETER temperature 0.7",
        "",
        f'SYSTEM """{persona.to_prompt()}"""',
    ]
    return "\n".join(lines)


def export_hub(persona: Persona) -> str:
    """Export as PERSONA HUB compatible format."""
    hub_format = {
        "persona": persona.description,
        "traits": persona.traits,
        "input_persona": f"You are {persona.name}. {persona.description}",
    }
    return json.dumps(hub_format, indent=2)


def _slugify(value: str) -> str:
    """Convert labels to schema-safe ids."""
    slug = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-._")
    return slug or "persona"


def _agentcy_context(persona: Persona) -> dict[str, Any]:
    """Return optional Agentcy export metadata."""
    context = persona.context.get("agentcy", {})
    return context if isinstance(context, dict) else {}


def _voice_array(*values: str) -> list[str]:
    """Normalize voice properties to stable string arrays."""
    normalized: list[str] = []
    for value in values:
        cleaned = value.strip()
        if cleaned and cleaned not in normalized:
            normalized.append(cleaned)
    return normalized


def _voice_values(agentcy: dict[str, Any], key: str, fallback: list[str]) -> list[str]:
    """Read optional Agentcy voice arrays with fallback values."""
    voice_value = agentcy.get("voice")
    voice = voice_value if isinstance(voice_value, dict) else {}
    items = voice.get(key)
    if isinstance(items, list):
        return _voice_array(*[str(item) for item in items]) or fallback
    return fallback


def _build_constraints(persona: Persona, agentcy: dict[str, Any]) -> dict[str, Any]:
    """Build schema-aligned constraint block."""
    constraints_value = agentcy.get("constraints")
    raw_constraints = constraints_value if isinstance(constraints_value, dict) else {}
    dos = list(raw_constraints.get("dos", []))
    donts = list(raw_constraints.get("donts", []))

    if not dos:
        dos = ["stay consistent with the persona summary and stated traits"]
    if not donts:
        donts = persona.boundaries[:] or ["break the stated persona boundaries"]

    constraints: dict[str, Any] = {"dos": dos, "donts": donts}
    lexicon_value = raw_constraints.get("lexicon")
    raw_lexicon = lexicon_value if isinstance(lexicon_value, dict) else {}
    preferred = list(raw_lexicon.get("preferred", []))
    avoid = list(raw_lexicon.get("avoid", []))
    if preferred or avoid:
        constraints["lexicon"] = {"preferred": preferred, "avoid": avoid}
    return constraints


def export_voice_pack(persona: Persona) -> str:
    """Export as canonical Agentcy voice_pack.v1 JSON."""
    agentcy = _agentcy_context(persona)
    persona_slug = _slugify(persona.name)
    voice_pack = {
        "artifact_type": "voice_pack.v1",
        "schema_version": "v1",
        "voice_pack_id": agentcy.get(
            "voice_pack_id", f"{persona_slug}.voice.default.v{persona.version}"
        ),
        "brand_id": agentcy.get("brand_id", f"{persona_slug}.brand.core"),
        "writer": {
            "repo": "cli-prsna",
            "module": "agentcy-vox",
        },
        "name": persona.name,
        "summary": persona.description or f"Voice pack for {persona.name}",
        "voice": {
            "tone": _voice_values(agentcy, "tone", _voice_array(persona.voice.tone)),
            "style": _voice_values(
                agentcy,
                "style",
                _voice_array(persona.voice.vocabulary, *persona.voice.patterns),
            ),
            "audience": _voice_values(
                agentcy,
                "audience",
                _voice_array(*agentcy.get("audience", ["general audience"])),
            ),
        },
        "constraints": _build_constraints(persona, agentcy),
    }

    if persona.traits:
        voice_pack["traits"] = list(dict.fromkeys(persona.traits))

    examples = [
        {"label": ex.get("user", f"example {index}"), "text": _get_response(ex)}
        for index, ex in enumerate(persona.examples, start=1)
        if ex.get("user") and _get_response(ex)
    ]
    if examples:
        voice_pack["examples"] = examples

    source = agentcy.get("source") if isinstance(agentcy.get("source"), dict) else {}
    if source:
        voice_pack["source"] = source

    return json.dumps(voice_pack, indent=2, sort_keys=False)


_EXPORTERS: dict[str, Callable[[Persona], str]] = {
    "prompt": export_prompt,
    "eliza": export_eliza,
    "v2": export_v2,
    "ollama": export_ollama,
    "hub": export_hub,
    "voice-pack": export_voice_pack,
    "voice-pack.v1": export_voice_pack,
    "voice_pack": export_voice_pack,
    "voice_pack.v1": export_voice_pack,
}


def get_exporter(format: str) -> Callable[[Persona], str]:
    """Get exporter function by format name."""
    if format not in _EXPORTERS:
        raise KeyError(f"Unknown format: {format}")
    return _EXPORTERS[format]


def list_formats() -> list[str]:
    """List available export formats."""
    return list(_EXPORTERS.keys())
