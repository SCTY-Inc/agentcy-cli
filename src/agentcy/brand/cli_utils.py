from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

import click
import typer
import yaml
from pydantic import BaseModel
from rich.console import Console
from rich.pretty import Pretty


@dataclass
class OutputMode:
    json: bool = False
    envelope: bool = False


_output = OutputMode()
_console = Console()
_err_console = Console(stderr=True)


def set_output_mode(*, json_output: bool, envelope: bool = False) -> None:
    _output.json = json_output or envelope
    _output.envelope = envelope


def set_json_output(enabled: bool) -> None:
    set_output_mode(json_output=enabled)


def is_json_output() -> bool:
    return _output.json


def is_json_envelope_output() -> bool:
    return _output.envelope


def pick_format(format: str | None, default: str = "json") -> str:
    if format:
        return format
    return "json" if _output.json else default


def status(message: Any) -> None:
    if _output.json:
        _err_console.print(message)
    else:
        _console.print(message)


def emit(data: Any, format: str | None = None, *, default: str = "json") -> str | None:
    normalized = _normalize(data)
    resolved = pick_format(format, default=default)
    if resolved == "json":
        payload_data = _json_envelope(normalized) if _output.envelope else normalized
        payload = json.dumps(payload_data, indent=2, ensure_ascii=False)
        typer.echo(payload)
        return payload
    if resolved == "yaml":
        payload = yaml.safe_dump(normalized, sort_keys=False)
        typer.echo(payload)
        return payload

    _console.print(Pretty(normalized))
    return None


def scope_note(message: str) -> None:
    status(f"[yellow]{message}[/yellow]")


def _json_envelope(data: Any) -> dict[str, Any]:
    return {
        "status": "ok",
        "command": _command_name(),
        "data": data,
    }


def _command_name() -> str:
    ctx = click.get_current_context(silent=True)
    if ctx is None:
        return "compass"
    parts = ctx.command_path.split()
    if parts and parts[0] == "agentcy-compass":
        parts = parts[1:]
    return ".".join(parts) or "compass"


def _normalize(data: Any) -> Any:
    if isinstance(data, BaseModel):
        return data.model_dump()
    if isinstance(data, dict):
        return data
    if hasattr(data, "model_dump"):
        return data.model_dump()
    return data
