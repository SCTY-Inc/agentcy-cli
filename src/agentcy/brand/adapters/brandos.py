from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentcy.brand.core.identity import BrandProfile, Identity, Voice


def load_profile(config_path: str | Path, brand_key: str) -> BrandProfile:
    payload = _load_yaml(config_path)
    profile = payload.get(brand_key, {}) or {}

    identity = Identity(
        name=brand_key,
        description=profile.get("company_summary"),
        voice=Voice(),
        metadata={"source": "brandos"},
    )

    return BrandProfile(
        identity=identity,
        keywords=profile.get("keywords") or [],
        competitors=profile.get("competitors") or [],
        stop_phrases=profile.get("stop_phrases") or [],
        metadata={"source": "brandos"},
    )


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).expanduser().open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
