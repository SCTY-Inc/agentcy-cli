from __future__ import annotations

import os
from pathlib import Path


def default_data_dir(home: Path | None = None) -> Path:
    """Return the current default runtime data dir compatibility path."""
    home = home or Path.home()
    return home / ".brand-os"


def resolve_data_dir() -> Path:
    """Resolve the active runtime data dir without changing compatibility behavior."""
    root = os.getenv("BRANDOS_DATA_DIR")
    return Path(root).expanduser() if root else default_data_dir()


def data_dir() -> Path:
    path = resolve_data_dir()
    path.mkdir(parents=True, exist_ok=True)
    return path


def output_dir() -> Path:
    path = data_dir() / "outputs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def identities_dir() -> Path:
    path = data_dir() / "identities"
    path.mkdir(parents=True, exist_ok=True)
    return path


def ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_output_path(filename: str, directory: Path | None = None) -> Path:
    base = directory or output_dir()
    return base / filename
