"""Utility functions for agentcy-voice."""

from __future__ import annotations

import json


def parse_llm_json(content: str, default: dict | None = None) -> dict:
    """Safely parse JSON from LLM response.

    Args:
        content: Raw string content from LLM
        default: Default value if parsing fails (None raises exception)

    Returns:
        Parsed dict

    Raises:
        ValueError: If parsing fails and no default provided
    """
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        if default is not None:
            return default
        raise ValueError(f"Invalid JSON from LLM: {content[:200]}...") from e
