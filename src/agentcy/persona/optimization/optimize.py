"""Persona optimization and testing."""

from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

import dspy

if TYPE_CHECKING:
    from agentcy.persona.persona import Persona


def persona_fidelity_metric(example: dspy.Example, prediction: dspy.Prediction) -> float:
    """Measure how well a response matches persona expectations.

    Returns a score between 0 and 1.
    """
    from agentcy.persona.optimization.dspy_modules import PersonaConsistency

    evaluator = dspy.ChainOfThought(PersonaConsistency)

    result = evaluator(
        persona=example.persona,
        response=prediction.response,
    )

    return 1.0 if result.consistent else 0.0


def test_persona(
    persona: Persona,
    test_messages: list[str] | None = None,
    num_samples: int = 10,
    *,
    cases: list[dict] | None = None,
    difficulty: str = "mixed",
) -> dict:
    """Test persona consistency across explicit eval cases.

    Args:
        persona: The persona to test
        test_messages: Custom test messages (optional)
        num_samples: Number of generated samples when custom cases are not supplied
        cases: Structured eval cases (optional)
        difficulty: Generated case tier: basic, mixed, or stress

    Returns:
        Dict with aggregate scores and detailed failure signals
    """
    from agentcy.persona.drift import detect_drift
    from agentcy.persona.eval_cases import generate_eval_cases
    from agentcy.persona.optimization.dspy_modules import PersonaChat

    if cases is None:
        if test_messages:
            cases = [
                {
                    "case_id": f"custom.{index:02d}",
                    "bucket": "custom",
                    "difficulty": "custom",
                    "user_message": message,
                    "expected_dimensions": [],
                }
                for index, message in enumerate(test_messages, start=1)
            ]
        else:
            cases = generate_eval_cases(persona, difficulty=difficulty, limit=num_samples)

    chat = PersonaChat(persona.to_prompt())
    results = []

    for case in cases:
        prediction = chat(message=case["user_message"])
        drift = detect_drift(persona, prediction.response)
        score = max(0.0, 1.0 - drift.drift_score)
        results.append(
            {
                "case_id": case["case_id"],
                "bucket": case["bucket"],
                "difficulty": case["difficulty"],
                "expected_dimensions": list(case.get("expected_dimensions", [])),
                "message": case["user_message"],
                "response": prediction.response,
                "score": score,
                "passed": drift.consistent,
                "issues": drift.issues,
                "dimension_scores": drift.dimension_scores,
            }
        )

    scores = [r["score"] for r in results]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    bucket_scores: dict[str, float] = {}
    bucket_totals: dict[str, list[float]] = defaultdict(list)
    difficulty_scores: dict[str, float] = {}
    difficulty_totals: dict[str, list[float]] = defaultdict(list)
    failure_modes: list[str] = []

    for result in results:
        bucket_totals[result["bucket"]].append(result["score"])
        difficulty_totals[result["difficulty"]].append(result["score"])
        for issue in result["issues"]:
            if issue not in failure_modes:
                failure_modes.append(issue)

    for bucket, values in bucket_totals.items():
        bucket_scores[bucket] = sum(values) / len(values)
    for bucket, values in difficulty_totals.items():
        difficulty_scores[bucket] = sum(values) / len(values)

    boundary_cases = [
        result
        for result in results
        if "boundary_respect" in result["expected_dimensions"]
    ]
    boundary_pass_rate = (
        sum(1 for result in boundary_cases if result["passed"]) / len(boundary_cases)
        if boundary_cases
        else 1.0
    )

    return {
        "persona": persona.name,
        "difficulty": difficulty,
        "score": avg_score,
        "passed": sum(1 for result in results if result["passed"]),
        "failed": sum(1 for result in results if not result["passed"]),
        "total": len(results),
        "bucket_scores": bucket_scores,
        "difficulty_scores": difficulty_scores,
        "boundary_pass_rate": boundary_pass_rate,
        "failure_modes": failure_modes,
        "details": results,
    }


def optimize_persona(
    persona: Persona,
    trainset: list[dspy.Example],
    valset: list[dspy.Example] | None = None,
    max_iterations: int = 50,
) -> Persona:
    """Optimize persona prompt using GEPA.

    Args:
        persona: The persona to optimize
        trainset: Training examples
        valset: Validation examples (optional)
        max_iterations: Maximum optimization iterations

    Returns:
        Persona with optimized description/traits
    """
    try:
        import gepa
    except ImportError:
        raise ImportError("gepa required: pip install gepa")

    seed_candidate = {"persona_prompt": persona.to_prompt()}

    result = gepa.optimize(
        seed_candidate=seed_candidate,
        trainset=trainset,
        valset=valset or trainset,
        task_lm="openai/gpt-4o-mini",
        reflection_lm="openai/gpt-4o",
        max_metric_calls=max_iterations,
    )

    # Update persona description with optimized prompt
    optimized_prompt = result.best_candidate["persona_prompt"]
    persona.description = optimized_prompt

    return persona
