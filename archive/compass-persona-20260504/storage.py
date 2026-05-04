"""Persona persistence helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from brand_os.core.storage import data_dir


def personas_dir() -> Path:
    """Get the personas directory."""
    path = data_dir() / "personas"
    path.mkdir(parents=True, exist_ok=True)
    return path


def list_personas() -> list[str]:
    """List all available personas."""
    pdir = personas_dir()
    return sorted(p.stem for p in pdir.glob("*.yaml") if not p.name.startswith("."))


def get_persona_path(name: str) -> Path:
    """Get the path to a persona file."""
    return personas_dir() / f"{name}.yaml"


def load_persona(name: str) -> dict[str, Any]:
    """Load a persona by name."""
    path = get_persona_path(name)
    if not path.exists():
        raise ValueError(f"Persona not found: {name}")
    with open(path) as f:
        return yaml.safe_load(f) or {}


def save_persona(name: str, data: dict[str, Any]) -> Path:
    """Save a persona to disk."""
    path = get_persona_path(name)
    with open(path, "w") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    return path


def delete_persona(name: str) -> bool:
    """Delete a persona by name."""
    path = get_persona_path(name)
    if path.exists():
        path.unlink()
        return True
    return False
