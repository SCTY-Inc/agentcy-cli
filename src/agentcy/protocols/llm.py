"""Shared LLM interface protocol for the agentcy suite.

Each member implements its own provider (litellm in vox, subprocess API in compass,
CLI bridge in echo) but all should satisfy this structural interface.
"""

from __future__ import annotations

from typing import Any, Protocol


class LLMError(Exception):
    """Base exception for LLM failures across all agentcy members."""


class LLMProvider(Protocol):
    """Structural interface every agentcy LLM provider should satisfy."""

    def complete(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
    ) -> str: ...

    def complete_json(
        self,
        prompt: str,
        system: str | None = None,
        model: str | None = None,
        default: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...
