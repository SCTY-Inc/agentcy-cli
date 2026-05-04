"""Persona optimization using DSPy and GEPA."""
from __future__ import annotations

from typing import Any

from brand_os.persona.crud import load_persona, save_persona


def optimize_persona(
    persona_name: str,
    test_cases: list[dict[str, str]] | None = None,
    method: str = "dspy",
) -> dict[str, Any]:
    """Optimize a persona using automated methods.

    Args:
        persona_name: Name of the persona to optimize
        test_cases: Optional list of test cases with input/expected pairs
        method: Optimization method ("dspy" or "gepa")

    Returns:
        Optimized persona

    Requires: dspy optional dependency
    """
    if method == "dspy":
        return _optimize_with_dspy(persona_name, test_cases)
    elif method == "gepa":
        return _optimize_with_gepa(persona_name, test_cases)
    else:
        raise ValueError(f"Unknown optimization method: {method}")


def _optimize_with_dspy(
    persona_name: str,
    test_cases: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Optimize using DSPy."""
    try:
        import dspy
    except ImportError:
        raise ImportError("dspy required for optimization. Install with: pip install agentcy-compass[optimize]")

    persona = load_persona(persona_name)

    # Define DSPy signature for persona chat
    class PersonaChat(dspy.Signature):
        """Chat as a specific persona."""
        persona_traits: str = dspy.InputField(desc="Comma-separated persona traits")
        persona_voice: str = dspy.InputField(desc="Voice tone and style")
        user_input: str = dspy.InputField(desc="User's message")
        response: str = dspy.OutputField(desc="Persona's response")

    # Create module
    class PersonaModule(dspy.Module):
        def __init__(self):
            super().__init__()
            self.generate = dspy.ChainOfThought(PersonaChat)

        def forward(self, persona_traits: str, persona_voice: str, user_input: str):
            return self.generate(
                persona_traits=persona_traits,
                persona_voice=persona_voice,
                user_input=user_input,
            )

    # TODO: Full DSPy optimization loop with test cases
    # For now, return the persona unchanged
    return persona


def _optimize_with_gepa(
    persona_name: str,
    test_cases: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Optimize using GEPA (Genetic-Pareto) algorithm."""
    try:
        import gepa
    except ImportError:
        raise ImportError("gepa required for GEPA optimization. Install with: pip install agentcy-compass[optimize]")

    persona = load_persona(persona_name)

    # TODO: Full GEPA optimization loop
    # For now, return the persona unchanged
    return persona


def test_persona_consistency(
    persona_name: str,
    test_cases: list[dict[str, str]],
) -> dict[str, Any]:
    """Test persona consistency across test cases.

    Args:
        persona_name: Name of the persona
        test_cases: List of dicts with 'input' and optional 'expected' keys

    Returns:
        Test results with pass/fail for each case
    """
    from brand_os.persona.chat import ask
    from brand_os.persona.drift import detect_drift

    results = {
        "total": len(test_cases),
        "passed": 0,
        "failed": 0,
        "cases": [],
    }

    for case in test_cases:
        user_input = case.get("input", "")
        expected = case.get("expected")

        # Get response
        response = ask(persona_name, user_input)

        # Check drift
        drift = detect_drift(persona_name, response, context=user_input)

        case_result = {
            "input": user_input,
            "response": response,
            "expected": expected,
            "is_consistent": drift.is_consistent,
            "confidence": drift.confidence,
            "passed": drift.is_consistent and drift.confidence > 0.7,
        }

        results["cases"].append(case_result)
        if case_result["passed"]:
            results["passed"] += 1
        else:
            results["failed"] += 1

    return results
