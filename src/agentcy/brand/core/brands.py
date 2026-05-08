"""Brand discovery and resolution."""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentcy.brand.core.config import get_config
from agentcy.brand.core.identity import BrandProfile, Identity, Visual, Voice


def get_brands_dir() -> Path:
    """Get the brands directory."""
    config = get_config()
    brands_dir = config.brands_dir
    if not brands_dir.is_absolute():
        brands_dir = Path.cwd() / brands_dir
    return brands_dir


def discover_brands() -> list[str]:
    """Discover all available brands in the brands directory."""
    brands_dir = get_brands_dir()
    if not brands_dir.exists():
        return []

    brands = []
    for item in brands_dir.iterdir():
        if item.is_dir() and not item.name.startswith(("_", ".")):
            # Check for brand.yml or <name>-brand.yml
            if (item / "brand.yml").exists() or (item / f"{item.name}-brand.yml").exists():
                brands.append(item.name)

    return sorted(brands)


def get_brand_dir(name: str) -> Path:
    """Get the directory for a specific brand."""
    return get_brands_dir() / name


def resolve_brand(name: str) -> Path | None:
    """Resolve a brand name to its directory path."""
    brand_dir = get_brand_dir(name)
    if brand_dir.exists():
        return brand_dir
    return None


def load_brand_config(name: str) -> dict[str, Any]:
    """Load the brand configuration YAML."""
    brand_dir = resolve_brand(name)
    if not brand_dir:
        raise ValueError(f"Brand not found: {name}")

    # Try both naming conventions
    for filename in ["brand.yml", f"{name}-brand.yml"]:
        config_path = brand_dir / filename
        if config_path.exists():
            with open(config_path) as f:
                return yaml.safe_load(f) or {}

    raise ValueError(f"No brand.yml found for: {name}")


def load_brand_profile(name: str) -> BrandProfile:
    """Load a brand as a BrandProfile object."""
    config = load_brand_config(name)

    # Build Identity from config
    identity = Identity(
        name=config.get("name", name),
        description=config.get("description"),
        traits=config.get("traits", []),
        boundaries=config.get("boundaries", []),
        voice=Voice(**config.get("voice", {})) if config.get("voice") else Voice(),
    )

    # Build Visual if present
    visual = None
    if "visual" in config:
        visual = Visual(**config["visual"])

    return BrandProfile(
        identity=identity,
        visual=visual,
        platforms=config.get("platforms"),
        handles=config.get("handles"),
        keywords=config.get("keywords"),
        competitors=config.get("competitors"),
        stop_phrases=config.get("stop_phrases"),
    )


def load_brand_rubric(name: str) -> dict[str, Any]:
    """Load the rubric YAML for a brand."""
    brand_dir = resolve_brand(name)
    if not brand_dir:
        raise ValueError(f"Brand not found: {name}")

    # Try both naming conventions
    for filename in ["rubric.yml", f"{name}-rubric.yml"]:
        rubric_path = brand_dir / filename
        if rubric_path.exists():
            with open(rubric_path) as f:
                return yaml.safe_load(f) or {}

    return {}


def get_brand_asset_dir(name: str) -> Path:
    """Get the assets directory for a brand."""
    brand_dir = resolve_brand(name)
    if not brand_dir:
        raise ValueError(f"Brand not found: {name}")
    return brand_dir / "assets"


def get_brand_intel_dir(name: str) -> Path:
    """Get the intel directory for a brand."""
    brand_dir = resolve_brand(name)
    if not brand_dir:
        raise ValueError(f"Brand not found: {name}")
    intel_dir = brand_dir / "intel"
    intel_dir.mkdir(exist_ok=True)
    return intel_dir
