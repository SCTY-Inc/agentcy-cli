from __future__ import annotations

import re
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


class EvalResult(BaseModel):
    passed: bool
    score: float
    dimension_scores: dict[str, float] = Field(default_factory=dict)
    banned_matches: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def evaluate_with_scores(
    text: str,
    rubric: Rubric,
    dimension_scores: dict[str, float],
) -> EvalResult:
    base_score = _weighted_score(rubric, dimension_scores)
    banned = detect_banned_phrases(text, rubric.banned_phrases)
    red_flags = detect_red_flags(text, rubric.red_flag_patterns)

    penalty = 0.0
    if banned:
        penalty += 100.0
    penalty += sum(flag[1] for flag in red_flags)

    final_score = max(0.0, base_score - penalty)
    passed = final_score >= rubric.threshold and not banned

    return EvalResult(
        passed=passed,
        score=final_score,
        dimension_scores=dimension_scores,
        banned_matches=banned,
        red_flags=[flag[0] for flag in red_flags],
        metadata={"base_score": base_score, "penalty": penalty},
    )


def _weighted_score(rubric: Rubric, dimension_scores: dict[str, float]) -> float:
    if not rubric.dimensions:
        return 0.0

    total_weight = sum(dim.weight for dim in rubric.dimensions.values() if dim.weight > 0)
    if total_weight == 0:
        total_weight = float(len(rubric.dimensions))

    weighted_sum = 0.0
    for key, dimension in rubric.dimensions.items():
        score = dimension_scores.get(key, 0.0)
        weight = dimension.weight if dimension.weight > 0 else 1.0
        weighted_sum += score * weight

    normalized = weighted_sum / total_weight
    return max(0.0, min(100.0, (normalized / 10.0) * 100.0))


def detect_banned_phrases(text: str, banned_phrases: list[str]) -> list[str]:
    if not banned_phrases:
        return []

    lowered = text.lower()
    return [phrase for phrase in banned_phrases if phrase.lower() in lowered]


def detect_red_flags(text: str, patterns: list[RedFlagPattern]) -> list[tuple[str, float]]:
    if not patterns:
        return []

    matches: list[tuple[str, float]] = []
    for pattern in patterns:
        if re.search(pattern.pattern, text, flags=re.IGNORECASE):
            matches.append((pattern.reason, pattern.penalty))
    return matches
