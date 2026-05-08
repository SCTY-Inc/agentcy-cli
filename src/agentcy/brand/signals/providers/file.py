"""File-based signal provider."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from agentcy.brand.core.config import utc_now


def load_signals_from_file(path: Path) -> list[dict[str, Any]]:
    """Load signals from a JSON or YAML file.

    Args:
        path: Path to signals file

    Returns:
        List of signal dicts
    """
    if not path.exists():
        return []

    content = path.read_text()

    if path.suffix in (".yaml", ".yml"):
        data = yaml.safe_load(content) or []
    else:
        data = json.loads(content)

    # Ensure it's a list
    if isinstance(data, dict):
        data = data.get("signals", [])

    # Add source info
    for signal in data:
        if "source" not in signal:
            signal["source"] = "file"
        if "loaded_from" not in signal:
            signal["loaded_from"] = str(path)

    return data


def save_signals_to_file(
    signals: list[dict[str, Any]],
    path: Path,
    append: bool = False,
) -> int:
    """Save signals to a file.

    Args:
        signals: List of signals to save
        path: Output path
        append: If True, append to existing file

    Returns:
        Number of signals saved
    """
    if append and path.exists():
        existing = load_signals_from_file(path)
        signals = existing + signals

    # Add timestamp
    for signal in signals:
        if "saved_at" not in signal:
            signal["saved_at"] = utc_now().isoformat()

    if path.suffix in (".yaml", ".yml"):
        content = yaml.dump(signals, default_flow_style=False, allow_unicode=True)
    else:
        content = json.dumps(signals, indent=2, ensure_ascii=False)

    path.write_text(content)
    return len(signals)
