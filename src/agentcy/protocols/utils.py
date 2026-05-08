"""Shared JSON utilities for the agentcy protocol layer."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any


def load_json(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_json_optional(path: Path | str | None) -> dict[str, Any] | None:
    if path is None:
        return None
    p = Path(path)
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def write_json(path: Path | str, data: dict[str, Any]) -> Path:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return p


def parse_llm_json(text: str, default: dict[str, Any] | None = None) -> dict[str, Any]:
    """Extract JSON from an LLM response, handling markdown code blocks.

    Tries three strategies in order:
    1. JSON inside a fenced code block (```json ... ``` or ``` ... ```)
    2. The outermost ``{...}`` substring
    3. Raw ``json.loads``

    Returns *default* (or ``{}``) when all strategies fail and *default*
    is not ``None``; raises ``ValueError`` otherwise.
    """
    # 1. fenced code block
    json_match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if json_match:
        text = json_match.group(1)

    # 2. outermost object braces
    obj_match = re.search(r"\{[\s\S]*\}", text)
    if obj_match:
        text = obj_match.group(0)

    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        if default is not None:
            return default
        raise ValueError(f"Invalid JSON from LLM: {text[:200]}") from exc
