"""Persona chat and conversation API."""
from __future__ import annotations

from typing import Any, Iterator

from brand_os.core.llm import complete, get_provider
from brand_os.persona.crud import load_persona


def build_system_prompt(persona: dict[str, Any]) -> str:
    """Build a system prompt from persona definition."""
    parts = [f"You are {persona.get('name', 'an assistant')}."]

    if desc := persona.get("description"):
        parts.append(desc)

    if traits := persona.get("traits"):
        parts.append(f"Your key traits: {', '.join(traits)}.")

    voice = persona.get("voice", {})
    if tone := voice.get("tone"):
        parts.append(f"Speak in a {tone} tone.")
    if vocab := voice.get("vocabulary"):
        parts.append(f"Use {vocab} vocabulary.")
    if patterns := voice.get("patterns"):
        parts.append(f"Follow these patterns: {'; '.join(patterns)}.")

    if boundaries := persona.get("boundaries"):
        parts.append(f"Boundaries: {'; '.join(boundaries)}.")

    if examples := persona.get("examples"):
        parts.append("\nExample interactions:")
        for ex in examples[:3]:
            parts.append(f"User: {ex.get('user', ex.get('input', ''))}")
            parts.append(f"You: {ex.get('assistant', ex.get('output', ''))}")

    return "\n".join(parts)


def chat(
    persona_name: str,
    message: str,
    history: list[dict[str, str]] | None = None,
    model: str | None = None,
) -> str:
    """Send a message to a persona and get a response."""
    persona = load_persona(persona_name)
    system = build_system_prompt(persona)

    # Build full prompt with history
    prompt_parts = []
    if history:
        for msg in history:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            prompt_parts.append(f"{role.title()}: {content}")

    prompt_parts.append(f"User: {message}")
    prompt_parts.append("Assistant:")

    full_prompt = "\n".join(prompt_parts)

    # Get model from persona or use default
    if model is None:
        providers = persona.get("providers", {})
        model = providers.get("default")

    return complete(prompt=full_prompt, system=system, model=model)


def ask(persona_name: str, prompt: str, model: str | None = None) -> str:
    """One-shot query to a persona (no history)."""
    return chat(persona_name, prompt, history=None, model=model)


class Conversation:
    """Manages a conversation session with a persona."""

    def __init__(self, persona_name: str, model: str | None = None):
        self.persona_name = persona_name
        self.model = model
        self.history: list[dict[str, str]] = []

    def send(self, message: str) -> str:
        """Send a message and get a response."""
        response = chat(
            self.persona_name,
            message,
            history=self.history,
            model=self.model,
        )

        # Update history
        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": response})

        return response

    def clear(self) -> None:
        """Clear conversation history."""
        self.history = []
