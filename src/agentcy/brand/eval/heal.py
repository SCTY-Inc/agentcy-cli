"""Self-healing content loop."""
from __future__ import annotations

from typing import Any

from agentcy.brand.core.llm import complete
from agentcy.brand.eval.grader import GradeResult, grade_content
from agentcy.brand.eval.rubric import Rubric


def heal_content(
    content: str,
    rubric: Rubric | None = None,
    max_iterations: int = 3,
    target_score: float = 0.8,
) -> dict[str, Any]:
    """Iteratively improve content until it passes.

    Args:
        content: Initial content
        rubric: Evaluation rubric
        max_iterations: Maximum improvement attempts
        target_score: Score to achieve

    Returns:
        Dict with final content, grades, and iteration history
    """
    history = []
    current_content = content

    for i in range(max_iterations):

        grade = grade_content(current_content, rubric)

        history.append({
            "iteration": i + 1,
            "content": current_content,
            "score": grade.overall_score,
            "passed": grade.passed,
            "suggestions": grade.suggestions,
        })


        if grade.overall_score >= target_score and grade.passed:
            return {
                "success": True,
                "final_content": current_content,
                "final_score": grade.overall_score,
                "iterations": i + 1,
                "history": history,
            }


        current_content = _improve_content(current_content, grade)

    # Final grade after all iterations
    final_grade = grade_content(current_content, rubric)

    return {
        "success": final_grade.overall_score >= target_score,
        "final_content": current_content,
        "final_score": final_grade.overall_score,
        "iterations": max_iterations,
        "history": history,
    }


def _improve_content(content: str, grade: GradeResult) -> str:
    """Improve content based on grade feedback.

    Args:
        content: Current content
        grade: Grade result with feedback

    Returns:
        Improved content
    """
    prompt_parts = [
        "Improve this content based on the feedback.",
        "",
        "## Current Content",
        content,
        "",
        "## Feedback",
        f"Overall score: {grade.overall_score:.2f}",
        "",
        "### Dimension Feedback",
    ]

    for dim in grade.dimension_scores:
        if not dim.passed:
            prompt_parts.append(f"- {dim.name}: {dim.feedback}")

    if grade.red_flags_found:
        prompt_parts.extend([
            "",
            "### Red Flags to Fix",
            *[f"- {rf}" for rf in grade.red_flags_found],
        ])

    if grade.suggestions:
        prompt_parts.extend([
            "",
            "### Suggestions",
            *[f"- {s}" for s in grade.suggestions],
        ])

    prompt_parts.extend([
        "",
        "Rewrite the content addressing the feedback. Output ONLY the improved content, no explanations.",
    ])

    prompt = "\n".join(prompt_parts)

    return complete(
        prompt=prompt,
        system="You are a content improvement expert. Rewrite content to address feedback while maintaining the original intent and style.",
    )
