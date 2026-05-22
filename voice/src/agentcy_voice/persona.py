"""Core Persona class."""

from __future__ import annotations

from collections.abc import Generator, Iterator
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

from agentcy_voice.llm import DEFAULT_MODEL, complete_chat


class Voice(BaseModel):
    """Persona voice configuration."""

    tone: str = "neutral"
    vocabulary: str = "general"
    patterns: list[str] = Field(default_factory=list)


class DynamicSource(BaseModel):
    """Configuration for dynamic enrichment."""

    source: str = "exa"
    query: str | None = None
    refresh: str = "manual"  # manual, daily, weekly
    fields: list[str] = Field(default_factory=list)


class Persona(BaseModel):
    """A composable, testable AI persona."""

    name: str
    version: int = 1
    extends: str | None = None
    description: str = ""

    # Static traits
    traits: list[str] = Field(default_factory=list)
    voice: Voice = Field(default_factory=Voice)
    boundaries: list[str] = Field(default_factory=list)

    # Example dialogues
    examples: list[dict[str, str]] = Field(default_factory=list)

    # Dynamic enrichment
    dynamic: DynamicSource | None = None

    # Enriched context (populated by enrichment)
    context: dict[str, Any] = Field(default_factory=dict)

    # Provider preferences
    providers: dict[str, str] = Field(default_factory=lambda: {"default": DEFAULT_MODEL})

    def _get_model(self, override: str | None = None) -> str:
        """Get model to use, with optional override."""
        return override or self.providers.get("default", DEFAULT_MODEL)

    @classmethod
    @lru_cache(maxsize=32)
    def load(cls, path: Path | str) -> Persona:
        """Load persona from YAML file."""
        path = Path(path)
        with path.open() as f:
            data = yaml.safe_load(f)
        return cls(**data)

    def save(self, path: Path | str) -> None:
        """Save persona to YAML file."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w") as f:
            yaml.dump(self.model_dump(exclude_none=True), f, sort_keys=False)

    def to_prompt(self) -> str:
        """Convert persona to system prompt."""
        parts = []

        if self.description:
            parts.append(self.description)

        if self.traits:
            parts.append(f"Traits: {', '.join(self.traits)}")

        if self.voice.tone != "neutral":
            parts.append(f"Tone: {self.voice.tone}")

        if self.voice.vocabulary != "general":
            parts.append(f"Vocabulary: {self.voice.vocabulary}")

        if self.voice.patterns:
            parts.append(f"Speech patterns: {'; '.join(self.voice.patterns)}")

        if self.boundaries:
            parts.append("Boundaries:")
            for b in self.boundaries:
                parts.append(f"  - {b}")

        if self.context:
            parts.append("Current context:")
            for k, v in self.context.items():
                parts.append(f"  {k}: {v}")

        return "\n".join(parts)

    def merge_traits(self, other: Persona) -> Persona:
        """Merge traits from another persona."""
        return Persona(
            name=f"{self.name}+{other.name}",
            version=1,
            traits=list(set(self.traits + other.traits)),
            voice=self.voice,
            boundaries=list(set(self.boundaries + other.boundaries)),
            examples=self.examples + other.examples,
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Library API: Direct chat methods for programmatic use
    # ─────────────────────────────────────────────────────────────────────────

    def chat(
        self,
        message: str,
        model: str | None = None,
        history: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> str:
        """Single-turn chat with this persona."""
        messages = self._build_messages(message, history)
        return complete_chat(messages, model=self._get_model(model), **kwargs)

    def stream(
        self,
        message: str,
        model: str | None = None,
        history: list[dict[str, str]] | None = None,
        **kwargs: Any,
    ) -> Iterator[str]:
        """Streaming chat with this persona; yields response chunks."""
        messages = self._build_messages(message, history)
        response = complete_chat(messages, model=self._get_model(model), stream=True, **kwargs)
        for chunk in response:
            if chunk.choices and chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

    def conversation(self, model: str | None = None) -> "Conversation":
        """Return a multi-turn Conversation context manager for this persona."""
        return Conversation(self, self._get_model(model))

    def _build_messages(
        self, message: str, history: list[dict[str, str]] | None = None
    ) -> list[dict[str, str]]:
        """Build messages list for chat."""
        messages = [{"role": "system", "content": self.to_prompt()}]
        if history:
            messages.extend(history)
        messages.append({"role": "user", "content": message})
        return messages

    def generate(
        self,
        prompts: list[str],
        model: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """Batch generate responses for a list of prompts (same order preserved)."""
        return [self.chat(p, model=model, **kwargs) for p in prompts]

    def as_user(
        self,
        scenario: str,
        model: str | None = None,
        **kwargs: Any,
    ) -> str:
        """Flip persona to user role and generate a realistic user message for the scenario."""
        from agentcy_voice.llm import complete

        prompt = f"""You are roleplaying as this user persona:

{self.to_prompt()}

Generate a realistic user message for this scenario: {scenario}

Respond with ONLY the user message, no explanation or quotes."""

        return complete(prompt, model=self._get_model(model), **kwargs)


class Conversation:
    """Multi-turn conversation context manager."""

    def __init__(self, persona: Persona, model: str):
        self.persona = persona
        self.model = model
        self.history: list[dict[str, str]] = []

    def send(self, message: str, **kwargs: Any) -> str:
        """Send a message and get response."""
        response = self.persona.chat(message, model=self.model, history=self.history, **kwargs)
        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": response})
        return response

    def stream(self, message: str, **kwargs: Any) -> Generator[str, None, None]:
        """Send a message and stream response."""
        full_response = []
        for chunk in self.persona.stream(message, model=self.model, history=self.history, **kwargs):
            full_response.append(chunk)
            yield chunk
        # Add to history after complete
        self.history.append({"role": "user", "content": message})
        self.history.append({"role": "assistant", "content": "".join(full_response)})

    def reset(self) -> None:
        """Clear conversation history."""
        self.history = []

    def __enter__(self) -> "Conversation":
        return self

    def __exit__(self, *args: Any) -> None:
        pass
