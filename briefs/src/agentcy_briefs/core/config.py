"""Configuration loading and management."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from agentcy_protocols.utils import utc_now  # noqa: F401
from pydantic import BaseModel, Field

# Re-export the canonical helper. Briefs modules import it from this module;
# keep the local import path stable and let agentcy_protocols.utils own it.
__all_re_exports__ = ("utc_now",)


class BriefsConfig(BaseModel):
    """Global configuration for Briefs."""

    brands_dir: Path = Field(default_factory=lambda: Path("brands"))
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".agentcy" / "briefs")
    default_provider: str = "gemini"
    default_model: str | None = None


_config: BriefsConfig | None = None


def config_resolution_candidates(cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return config file candidates in load order."""
    cwd = cwd or Path.cwd()
    home = home or Path.home()
    return [
        cwd / "agentcy-briefs.yml",
        home / ".agentcy" / "briefs.yml",
    ]


def resolve_config_path(path: Path | None = None) -> Path | None:
    """Resolve the active config path."""
    if path is not None:
        return path

    env_path = os.getenv("AGENTCY_BRIEFS_CONFIG")
    if env_path:
        return Path(env_path)

    for candidate in config_resolution_candidates():
        if candidate.exists():
            return candidate

    return None


def resolve_workspace_path(path: Path) -> Path:
    """Resolve a relative workspace path by walking up from the current directory."""
    if path.is_absolute():
        return path

    cwd = Path.cwd()
    for root in [cwd, *cwd.parents]:
        candidate = root / path
        if candidate.exists():
            return candidate

    return cwd / path


def get_config() -> BriefsConfig:
    """Get the global configuration, loading from file if needed."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def load_config(path: Path | None = None) -> BriefsConfig:
    """Load configuration from YAML file."""
    path = resolve_config_path(path)

    if path and path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return BriefsConfig(**data)

    return BriefsConfig()


def get_env(key: str, default: str | None = None) -> str | None:
    """Get environment variable with AGENTCY_BRIEFS_ prefix."""
    return os.getenv(f"AGENTCY_BRIEFS_{key.upper()}", default)


def get_brands_dir() -> Path:
    """Get the brands directory."""
    config = get_config()
    return resolve_workspace_path(config.brands_dir)


def load_brand_config(brand: str) -> dict[str, Any] | None:
    """Load configuration for a specific brand.

    Args:
        brand: Brand name/slug

    Returns:
        Brand configuration dict or None if not found
    """
    brands_dir = get_brands_dir()
    brand_file = brands_dir / brand / "brand.yml"

    if not brand_file.exists():
        return None

    with open(brand_file) as f:
        return yaml.safe_load(f) or {}


def list_brands() -> list[str]:
    """List all available brands."""
    brands_dir = get_brands_dir()
    if not brands_dir.exists():
        return []

    return [
        d.name for d in brands_dir.iterdir()
        if d.is_dir() and (d / "brand.yml").exists() and not d.name.startswith("_")
    ]
