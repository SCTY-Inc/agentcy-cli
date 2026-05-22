"""Configuration loading and management."""
from __future__ import annotations

import os
from datetime import datetime  # noqa: F401  # re-exported for back-compat with importers
from pathlib import Path
from typing import Any

import yaml
from agentcy_protocols.utils import utc_now
from pydantic import BaseModel, Field

# Re-export the canonical helper. Compass historically defined a local copy of
# ``utc_now``; ~25 modules import it from this module. Keep the import path
# stable and let agentcy_protocols.utils own the implementation.
__all_re_exports__ = ("utc_now",)


class BrandOpsConfig(BaseModel):
    """Global configuration for brandos."""

    brands_dir: Path = Field(default_factory=lambda: Path("brands"))
    data_dir: Path = Field(default_factory=lambda: Path.home() / ".brandos")
    default_provider: str = "gemini"
    default_model: str | None = None


_config: BrandOpsConfig | None = None


def config_resolution_candidates(cwd: Path | None = None, home: Path | None = None) -> list[Path]:
    """Return the current compatibility-order config file candidates.

    This intentionally preserves the mixed current surface instead of migrating it.
    """
    cwd = cwd or Path.cwd()
    home = home or Path.home()
    return [
        cwd / "brandos.yml",
        home / ".brandos" / "config.yml",
    ]


def resolve_config_path(path: Path | None = None) -> Path | None:
    """Resolve the active config path using the current compatibility order."""
    if path is not None:
        return path

    env_path = os.getenv("BRANDOPS_CONFIG")
    if env_path:
        return Path(env_path)

    for candidate in config_resolution_candidates():
        if candidate.exists():
            return candidate

    return None


def get_config() -> BrandOpsConfig:
    """Get the global configuration, loading from file if needed."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def load_config(path: Path | None = None) -> BrandOpsConfig:
    """Load configuration from YAML file."""
    path = resolve_config_path(path)

    if path and path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return BrandOpsConfig(**data)

    return BrandOpsConfig()


def get_env(key: str, default: str | None = None) -> str | None:
    """Get environment variable with BRANDOPS_ prefix."""
    return os.getenv(f"BRANDOPS_{key.upper()}", default)


def get_brands_dir() -> Path:
    """Get the brands directory."""
    config = get_config()
    brands_dir = config.brands_dir
    if not brands_dir.is_absolute():
        brands_dir = Path.cwd() / brands_dir
    return brands_dir


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
