"""Learnings aggregation from evaluations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.llm import complete_json
from agentcy.brand.core.brands import get_brand_dir


def get_eval_log_path(brand: str) -> Path:
    """Get the evaluation log path for a brand."""
    brand_dir = get_brand_dir(brand)
    return brand_dir / "eval-log.jsonl"


def get_learnings_path(brand: str) -> Path:
    """Get the learnings file path for a brand."""
    brand_dir = get_brand_dir(brand)
    return brand_dir / "learnings.json"


def log_evaluation(
    brand: str,
    content: str,
    grade_result: dict[str, Any],
) -> None:
    """Log an evaluation for learning.

    Args:
        brand: Brand name
        content: Evaluated content
        grade_result: Grade result dict
    """
    log_path = get_eval_log_path(brand)

    entry = {
        "timestamp": utc_now().isoformat(),
        "content": content[:500],  # Truncate for storage
        "overall_score": grade_result.get("overall_score"),
        "passed": grade_result.get("passed"),
        "dimension_scores": grade_result.get("dimension_scores", []),
        "suggestions": grade_result.get("suggestions", []),
    }

    with open(log_path, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def load_eval_history(brand: str, limit: int = 100) -> list[dict[str, Any]]:
    """Load evaluation history for a brand.

    Args:
        brand: Brand name
        limit: Maximum entries to load

    Returns:
        List of evaluation entries
    """
    log_path = get_eval_log_path(brand)

    if not log_path.exists():
        return []

    entries = []
    with open(log_path) as f:
        for line in f:
            if line.strip():
                entries.append(json.loads(line))

    return entries[-limit:]


def aggregate_learnings(brand: str) -> dict[str, Any]:
    """Aggregate learnings from evaluation history.

    Args:
        brand: Brand name

    Returns:
        Aggregated learnings with patterns and suggestions
    """
    history = load_eval_history(brand, limit=50)

    if not history:
        return {
            "weak_dimensions": [],
            "common_suggestions": [],
            "patterns": [],
            "recommendations": [],
        }

    # Analyze with LLM
    prompt = f"""Analyze these content evaluations and identify patterns.

## Evaluation History
{json.dumps(history, indent=2)[:3000]}

Identify:
- weak_dimensions: dimensions that consistently score low
- common_suggestions: suggestions that appear frequently
- patterns: patterns in what works and what doesn't
- recommendations: specific recommendations for improvement

Output JSON."""

    default = {
        "weak_dimensions": [],
        "common_suggestions": [],
        "patterns": [],
        "recommendations": [],
    }

    learnings = complete_json(
        prompt=prompt,
        system="You are a content performance analyst. Identify patterns and actionable insights.",
        default=default,
    )

    # Save learnings
    learnings_path = get_learnings_path(brand)
    learnings["updated_at"] = utc_now().isoformat()
    learnings["entries_analyzed"] = len(history)
    learnings_path.write_text(json.dumps(learnings, indent=2, ensure_ascii=False))

    return learnings


def get_learnings(brand: str) -> dict[str, Any]:
    """Get current learnings for a brand.

    Args:
        brand: Brand name

    Returns:
        Learnings dict or empty dict if none
    """
    learnings_path = get_learnings_path(brand)

    if not learnings_path.exists():
        return {}

    return json.loads(learnings_path.read_text())


def get_weak_dimensions(brand: str) -> list[str]:
    """Get list of weak dimensions for a brand.

    Args:
        brand: Brand name

    Returns:
        List of dimension names that need improvement
    """
    learnings = get_learnings(brand)
    return learnings.get("weak_dimensions", [])


def get_improvement_suggestions(brand: str) -> list[str]:
    """Get improvement suggestions for a brand.

    Args:
        brand: Brand name

    Returns:
        List of suggestions
    """
    learnings = get_learnings(brand)
    suggestions = []
    suggestions.extend(learnings.get("common_suggestions", []))
    suggestions.extend(learnings.get("recommendations", []))
    return suggestions[:10]
