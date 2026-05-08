from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentcy.brand.core.identity import Example, Identity, Voice


def load_persona(path: str | Path) -> Identity:
    payload = _load_yaml(path)
    voice = Voice(**payload.get("voice", {}))
    examples = [Example(**item) for item in payload.get("examples", [])]
    return Identity(
        name=payload.get("name", Path(path).stem),
        description=payload.get("description"),
        traits=payload.get("traits", []) or [],
        boundaries=payload.get("boundaries", []) or [],
        examples=examples,
        voice=voice,
        metadata={"source": "persona", "version": payload.get("version")},
    )


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).expanduser().open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
