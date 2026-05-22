from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RubricDimension(BaseModel):
    weight: float
    description: str | None = None
    rubric: dict[str, str] | None = None


class RedFlagPattern(BaseModel):
    pattern: str
    reason: str
    penalty: float = 0.0


class Rubric(BaseModel):
    name: str
    version: str | None = None
    threshold: float = 0.0
    max_retries: int = 0
    dimensions: dict[str, RubricDimension] = Field(default_factory=dict)
    banned_phrases: list[str] = Field(default_factory=list)
    red_flag_patterns: list[RedFlagPattern] = Field(default_factory=list)
    judge_prompt: str | None = None
    platforms: dict[str, Any] | None = None
