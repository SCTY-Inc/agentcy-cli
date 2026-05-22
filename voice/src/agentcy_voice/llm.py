"""Centralized LLM interface with error handling."""

from __future__ import annotations

import logging
from typing import Any

import litellm

logger = logging.getLogger(__name__)

# Default settings
DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_TIMEOUT = 60


class LLMError(Exception):
    """Error from LLM completion."""

    pass


def complete(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system: str | None = None,
    history: list[dict[str, str]] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> str:
    """Complete a prompt via litellm; raises LLMError on failure."""
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": prompt})

    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            timeout=timeout,
            **kwargs,
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM completion failed: {e}")
        raise LLMError(f"Completion failed: {e}") from e


def complete_json(
    prompt: str,
    model: str = DEFAULT_MODEL,
    system: str | None = None,
    default: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
) -> dict:
    """Complete a prompt expecting JSON; returns default or raises LLMError on failure."""
    from agentcy_voice.utils import parse_llm_json

    content = complete(
        prompt=prompt,
        model=model,
        system=system,
        timeout=timeout,
        response_format={"type": "json_object"},
        **kwargs,
    )
    try:
        return parse_llm_json(content, default=default)
    except ValueError as e:
        if default is not None:
            logger.warning(f"LLM JSON parse failed, using default: {e}")
            return default
        raise LLMError(f"JSON parse failed: {e}") from e


def complete_chat(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    stream: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
):
    """Complete a chat; returns str or stream iterator. Raises LLMError on failure."""
    try:
        response = litellm.completion(
            model=model,
            messages=messages,
            stream=stream,
            timeout=timeout,
            **kwargs,
        )
        if stream:
            return response
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"LLM chat failed: {e}")
        raise LLMError(f"Chat completion failed: {e}") from e
