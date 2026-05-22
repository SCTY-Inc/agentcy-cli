"""Shared CLI output harness for the agentcy suite.

Provides a canonical {status, command, data} envelope and format-aware
emit functions. Import and wire into any member CLI.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class OutputState:
    json: bool = False
    envelope: bool = False
    command: str = ""


_state = OutputState()


def configure(*, json_output: bool, envelope: bool = False, command: str = "") -> None:
    """Call once at CLI startup to set global output mode."""
    _state.json = json_output or envelope
    _state.envelope = envelope
    _state.command = command


def is_json() -> bool:
    return _state.json


def is_envelope() -> bool:
    return _state.envelope


def normalize(data: Any) -> Any:
    """Coerce Pydantic models and model-like objects to plain dicts."""
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return data


def envelope(data: Any, *, command: str = "") -> dict[str, Any]:
    """Wrap data in canonical {status, command, data} envelope."""
    return {
        "status": "ok",
        "command": command or _state.command,
        "data": normalize(data),
    }


def emit(data: Any, *, command: str = "") -> str:
    """Emit data as JSON, wrapped in envelope if configured."""
    payload = normalize(data)
    if _state.envelope:
        payload = envelope(payload, command=command)
    output = json.dumps(payload, indent=2, ensure_ascii=False)
    print(output)
    return output


def emit_error(message: str, *, command: str = "", code: int = 1) -> str:
    """Emit a normalized error envelope and return JSON string."""
    payload = {
        "status": "error",
        "command": command or _state.command,
        "error": message,
        "code": code,
    }
    output = json.dumps(payload, indent=2, ensure_ascii=False)
    print(output)
    return output
