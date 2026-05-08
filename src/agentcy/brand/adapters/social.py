from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from agentcy.brand.core.evaluation import RedFlagPattern, Rubric, RubricDimension
from agentcy.brand.core.identity import BrandProfile, Identity, Visual, Voice


def load_brand(path: str | Path) -> BrandProfile:
    payload = _load_yaml(path)
    identity = Identity(
        name=payload.get("name", Path(path).stem),
        description=payload.get("description"),
        voice=Voice(),
        metadata={"source": "social"},
    )

    style = payload.get("style", {}) or {}
    visual = Visual(
        palette=style.get("colors"),
        typography=style.get("typography"),
        logo=style.get("logo"),
        prompt_override=style.get("prompt_override"),
        raw=style or None,
    ) if style else None

    return BrandProfile(
        identity=identity,
        visual=visual,
        platforms=payload.get("platforms"),
        handles=payload.get("handles"),
        metadata={"source": "social", "url": payload.get("url")},
    )


def load_rubric(path: str | Path) -> Rubric:
    payload = _load_yaml(path)
    dimensions = {
        key: RubricDimension(**value)
        for key, value in (payload.get("dimensions") or {}).items()
    }
    red_flags = [RedFlagPattern(**item) for item in payload.get("red_flag_patterns", [])]
    return Rubric(
        name=payload.get("name", Path(path).stem),
        version=payload.get("version"),
        threshold=payload.get("threshold", 0.0),
        max_retries=payload.get("max_retries", 0),
        dimensions=dimensions,
        banned_phrases=payload.get("banned_phrases", []) or [],
        red_flag_patterns=red_flags,
        judge_prompt=payload.get("judge_prompt"),
        platforms=payload.get("platforms"),
    )


def _load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).expanduser().open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle) or {}
