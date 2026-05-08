"""Content grading using LLM-as-judge."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentcy.brand.core.llm import complete_json
from agentcy.brand.eval.rubric import Rubric, get_default_rubric


class DimensionScore(BaseModel):
    """Score for a single dimension."""

    name: str
    score: float
    feedback: str
    passed: bool


class GradeResult(BaseModel):
    """Full grading result."""

    overall_score: float
    passed: bool
    dimension_scores: list[DimensionScore] = Field(default_factory=list)
    red_flags_found: list[str] = Field(default_factory=list)
    summary: str
    suggestions: list[str] = Field(default_factory=list)


GRADER_SYSTEM = """You are an expert content evaluator.
Grade the content against each dimension of the rubric.

For each dimension, provide:
- score: 0.0 to 1.0
- feedback: specific feedback
- passed: boolean (score >= threshold)

Also check for red flags and provide overall suggestions.

Output JSON with:
- dimension_scores: array of {name, score, feedback, passed}
- red_flags_found: array of any red flags detected
- summary: overall evaluation summary
- suggestions: array of improvement suggestions"""


def grade_content(
    content: str,
    rubric: Rubric | None = None,
    context: str | None = None,
) -> GradeResult:
    """Grade content against a rubric.

    Args:
        content: Content to grade
        rubric: Evaluation rubric (uses default if not provided)
        context: Optional context (brand, topic, etc.)

    Returns:
        GradeResult with scores and feedback
    """
    rubric = rubric or get_default_rubric()

    prompt_parts = [
        "Grade this content against the rubric.",
        "",
        "## Content",
        content,
        "",
        "## Rubric",
        f"Name: {rubric.name}",
        "",
        "### Dimensions",
    ]

    for dim in rubric.dimensions:
        prompt_parts.append(f"- **{dim.name}** (weight: {dim.weight}, threshold: {dim.threshold})")
        prompt_parts.append(f"  {dim.description}")
        if dim.criteria:
            prompt_parts.append(f"  Criteria: {', '.join(dim.criteria)}")

    if rubric.red_flags:
        prompt_parts.extend([
            "",
            "### Red Flags to Check",
            *[f"- {rf}" for rf in rubric.red_flags],
        ])

    if context:
        prompt_parts.extend(["", "## Context", context])

    prompt = "\n".join(prompt_parts)

    default = {
        "dimension_scores": [],
        "red_flags_found": [],
        "summary": "Unable to grade",
        "suggestions": [],
    }

    result = complete_json(prompt=prompt, system=GRADER_SYSTEM, default=default)


    dimension_scores = []
    total_weight = 0
    weighted_sum = 0

    for score_data in result.get("dimension_scores", []):
        dim_score = DimensionScore(
            name=score_data.get("name", ""),
            score=score_data.get("score", 0.0),
            feedback=score_data.get("feedback", ""),
            passed=score_data.get("passed", False),
        )
        dimension_scores.append(dim_score)

        # Find weight from rubric
        weight = 1.0
        for dim in rubric.dimensions:
            if dim.name.lower() == dim_score.name.lower():
                weight = dim.weight
                break

        weighted_sum += dim_score.score * weight
        total_weight += weight

    overall_score = weighted_sum / total_weight if total_weight > 0 else 0.0
    passed = overall_score >= rubric.pass_threshold and not result.get("red_flags_found")

    return GradeResult(
        overall_score=overall_score,
        passed=passed,
        dimension_scores=dimension_scores,
        red_flags_found=result.get("red_flags_found", []),
        summary=result.get("summary", ""),
        suggestions=result.get("suggestions", []),
    )


def quick_grade(content: str) -> float:
    """Quick grade returning just a score 0-1.

    Args:
        content: Content to grade

    Returns:
        Score 0-1
    """
    result = grade_content(content)
    return result.overall_score
