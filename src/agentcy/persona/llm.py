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
    """Complete a prompt with error handling.

    Args:
        prompt: User message
        model: Model to use
        system: Optional system message
        history: Optional conversation history
        timeout: Request timeout in seconds
        **kwargs: Passed to litellm.completion

    Returns:
        Response content string

    Raises:
        LLMError: On completion failure
    """
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
    """Complete a prompt expecting JSON response.

    Args:
        prompt: User message
        model: Model to use
        system: Optional system message
        default: Default value if parsing fails (None raises)
        timeout: Request timeout in seconds
        **kwargs: Passed to litellm.completion

    Returns:
        Parsed JSON dict

    Raises:
        LLMError: On completion or parse failure (if no default)
    """
    from agentcy.persona.utils import parse_llm_json

    try:
        content = complete(
            prompt=prompt,
            model=model,
            system=system,
            timeout=timeout,
            response_format={"type": "json_object"},
            **kwargs,
        )
        return parse_llm_json(content, default=default)
    except Exception as e:
        if default is not None:
            logger.warning(f"LLM JSON failed, using default: {e}")
            return default
        raise LLMError(f"JSON completion failed: {e}") from e


def complete_chat(
    messages: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
    stream: bool = False,
    timeout: int = DEFAULT_TIMEOUT,
    **kwargs: Any,
):
    """Complete a chat conversation.

    Args:
        messages: Full message list including system
        model: Model to use
        stream: Whether to stream response
        timeout: Request timeout in seconds
        **kwargs: Passed to litellm.completion

    Returns:
        Response content (str) or stream iterator

    Raises:
        LLMError: On completion failure
    """
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
