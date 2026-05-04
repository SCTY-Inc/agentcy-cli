"""Persona export formats."""
from __future__ import annotations

import json
from typing import Any

import yaml

from brand_os.persona.chat import build_system_prompt


def export_persona(persona: dict[str, Any], format: str) -> str:
    """Export a persona to a specific format.

    Supported formats:
    - json: Raw JSON
    - yaml: YAML format
    - eliza: ElizaOS character format
    - ollama: Ollama Modelfile format
    - hub: HuggingFace dataset format
    - v2: Enhanced YAML with metadata
    - system_prompt: Plain text system prompt
    - markdown: Markdown documentation
    """
    exporters = {
        "json": _export_json,
        "yaml": _export_yaml,
        "eliza": _export_eliza,
        "ollama": _export_ollama,
        "hub": _export_hub,
        "v2": _export_v2,
        "system_prompt": _export_system_prompt,
        "markdown": _export_markdown,
    }

    exporter = exporters.get(format.lower())
    if not exporter:
        raise ValueError(f"Unknown export format: {format}. Supported: {list(exporters.keys())}")

    return exporter(persona)


def _export_json(persona: dict[str, Any]) -> str:
    """Export as JSON."""
    return json.dumps(persona, indent=2, ensure_ascii=False)


def _export_yaml(persona: dict[str, Any]) -> str:
    """Export as YAML."""
    return yaml.dump(persona, default_flow_style=False, allow_unicode=True)


def _export_eliza(persona: dict[str, Any]) -> str:
    """Export as ElizaOS character format."""
    character = {
        "name": persona.get("name", "assistant"),
        "description": persona.get("description", ""),
        "personality": persona.get("traits", []),
        "voice": persona.get("voice", {}).get("tone", "neutral"),
        "system": build_system_prompt(persona),
        "examples": [
            {"user": ex.get("user", ex.get("input", "")),
             "agent": ex.get("assistant", ex.get("output", ""))}
            for ex in persona.get("examples", [])
        ],
    }
    return json.dumps(character, indent=2, ensure_ascii=False)


def _export_ollama(persona: dict[str, Any]) -> str:
    """Export as Ollama Modelfile format."""
    system_prompt = build_system_prompt(persona)
    lines = [
        f'FROM llama3.2',
        f'',
        f'PARAMETER temperature 0.7',
        f'',
        f'SYSTEM """',
        system_prompt,
        f'"""',
    ]
    return "\n".join(lines)


def _export_hub(persona: dict[str, Any]) -> str:
    """Export as HuggingFace dataset format (JSONL conversations)."""
    examples = persona.get("examples", [])
    system_prompt = build_system_prompt(persona)

    conversations = []
    for ex in examples:
        conv = {
            "conversations": [
                {"from": "system", "value": system_prompt},
                {"from": "human", "value": ex.get("user", ex.get("input", ""))},
                {"from": "gpt", "value": ex.get("assistant", ex.get("output", ""))},
            ]
        }
        conversations.append(json.dumps(conv, ensure_ascii=False))

    return "\n".join(conversations)


def _export_v2(persona: dict[str, Any]) -> str:
    """Export as enhanced v2 YAML with metadata."""
    v2_persona = {
        "schema_version": "2.0",
        "metadata": {
            "name": persona.get("name"),
            "version": persona.get("version", 1),
            "created_by": "brandos",
        },
        "identity": {
            "description": persona.get("description"),
            "traits": persona.get("traits", []),
            "boundaries": persona.get("boundaries", []),
        },
        "voice": persona.get("voice", {}),
        "examples": persona.get("examples", []),
        "context": persona.get("context", {}),
        "providers": persona.get("providers", {}),
    }
    return yaml.dump(v2_persona, default_flow_style=False, allow_unicode=True)


def _export_system_prompt(persona: dict[str, Any]) -> str:
    """Export as plain text system prompt."""
    return build_system_prompt(persona)


def _export_markdown(persona: dict[str, Any]) -> str:
    """Export as Markdown documentation."""
    lines = [
        f"# {persona.get('name', 'Persona')}",
        "",
        persona.get("description", ""),
        "",
        "## Traits",
        "",
    ]

    for trait in persona.get("traits", []):
        lines.append(f"- {trait}")

    lines.extend(["", "## Voice", ""])
    voice = persona.get("voice", {})
    if voice.get("tone"):
        lines.append(f"**Tone:** {voice['tone']}")
    if voice.get("vocabulary"):
        lines.append(f"**Vocabulary:** {voice['vocabulary']}")
    if patterns := voice.get("patterns"):
        lines.append(f"**Patterns:** {', '.join(patterns)}")

    if boundaries := persona.get("boundaries"):
        lines.extend(["", "## Boundaries", ""])
        for b in boundaries:
            lines.append(f"- {b}")

    if examples := persona.get("examples"):
        lines.extend(["", "## Example Interactions", ""])
        for i, ex in enumerate(examples, 1):
            lines.append(f"### Example {i}")
            lines.append(f"**User:** {ex.get('user', ex.get('input', ''))}")
            lines.append(f"**Assistant:** {ex.get('assistant', ex.get('output', ''))}")
            lines.append("")

    return "\n".join(lines)
