"""Bootstrap personas from descriptions, real people, or roles."""

from __future__ import annotations

import json

from agentcy.persona.clients import get_exa_client
from agentcy.persona.llm import DEFAULT_MODEL, complete_json

BOOTSTRAP_SYSTEM_PROMPT = """You are an expert at creating detailed AI personas.

Given a description, generate a complete persona specification as JSON with these fields:
- name: short identifier (lowercase, no spaces)
- description: 1-2 sentence summary of who this persona is
- traits: list of 4-6 personality traits
- voice: object with:
  - tone: communication style (e.g., "academic", "casual", "formal")
  - vocabulary: word choice level (e.g., "technical", "simple", "sophisticated")
  - patterns: list of 3-5 characteristic phrases they would use
- boundaries: list of 3-5 things this persona would NOT do or say
- examples: list of 2-3 example exchanges, each with "user" and "assistant" keys

Make the persona specific, memorable, and consistent. Avoid generic traits.
Output ONLY valid JSON, no markdown or explanation."""

PERSON_SYNTHESIS_PROMPT = """Based on the following information about a real person, create an AI persona that captures their communication style, thinking patterns, and expertise.

DO NOT create an impersonation. Instead, create a persona INSPIRED BY their approach - similar thinking style, domain expertise, and communication patterns, but clearly a distinct AI assistant.

Person information:
{context}

Generate a complete persona specification as JSON with these fields:
- name: a descriptive name (NOT the real person's name)
- description: 1-2 sentence summary capturing their approach/style
- traits: list of 4-6 personality traits evident from their work
- voice: object with:
  - tone: their communication style
  - vocabulary: their word choice patterns
  - patterns: list of 3-5 characteristic phrases/framings they use
- boundaries: list of 3-5 things reflecting their values/limits
- examples: list of 2-3 example exchanges showing their style

Output ONLY valid JSON, no markdown or explanation."""

PERSONA_REPAIR_PROMPT = """You are reviewing a persona JSON specification before it is saved.

Repair only concrete quality issues:
- contradictory traits or boundaries
- vague or generic voice patterns
- examples that do not match the description
- missing specificity that would make persona testing weak

Keep the same overall intent and shape. Return the repaired persona as JSON only."""


def _repair_persona_data(persona_data: dict, model: str) -> dict:
    repaired = complete_json(
        prompt=(
            "Review and repair this persona JSON for internal consistency and testability:\n\n"
            f"{json.dumps(persona_data, ensure_ascii=False, indent=2)}"
        ),
        model=model,
        system=PERSONA_REPAIR_PROMPT,
        default=persona_data,
    )

    merged = dict(persona_data)
    merged.update(repaired)

    if "context" in persona_data and "context" not in merged:
        merged["context"] = persona_data["context"]

    return merged


def bootstrap_from_description(
    description: str,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Generate persona from a text description.

    Args:
        description: Natural language description of desired persona
        model: LLM model to use for generation

    Returns:
        Dict with persona fields ready to create Persona object
    """
    persona_data = complete_json(
        prompt=f"Create a persona for: {description}",
        model=model,
        system=BOOTSTRAP_SYSTEM_PROMPT,
    )
    return _repair_persona_data(persona_data, model)


def bootstrap_from_person(
    query: str,
    model: str = DEFAULT_MODEL,
) -> dict:
    """Generate persona inspired by a real person via Exa search.

    Args:
        query: Person name and optional context (e.g., "Marc Andreessen VC")
        model: LLM model to use for synthesis

    Returns:
        Dict with persona fields
    """
    exa = get_exa_client()

    # Search for person
    results = exa.search(
        query,
        type="auto",
        category="people",
        num_results=5,
        use_autoprompt=True,
    )

    if not results.results:
        raise ValueError(f"No results found for: {query}")

    # Get content
    contents = exa.get_contents(
        [r.id for r in results.results[:3]],
        text={"max_characters": 3000},
        highlights={"num_sentences": 5},
    )

    # Build context from results
    context_parts = []
    for result in contents.results:
        if result.text:
            context_parts.append(result.text[:1500])
        if result.highlights:
            context_parts.extend(result.highlights)

    context = "\n\n".join(context_parts)

    # Synthesize persona
    persona_data = complete_json(
        prompt=f"Create a persona inspired by: {query}",
        model=model,
        system=PERSON_SYNTHESIS_PROMPT.format(context=context),
    )

    # Add source attribution
    persona_data["context"] = {
        "inspired_by": query,
        "sources": [r.url for r in results.results[:3]],
    }

    return _repair_persona_data(persona_data, model)


def bootstrap_from_role(
    role: str,
    company_context: str = "",
    model: str = DEFAULT_MODEL,
) -> dict:
    """Generate persona from a job role description.

    Args:
        role: Job title or role description
        company_context: Optional company/industry context
        model: LLM model to use

    Returns:
        Dict with persona fields
    """
    context = role
    if company_context:
        context = f"{role} at {company_context}"

    prompt = f"""Create a persona for someone in this role: {context}

Consider:
- How would someone in this role communicate?
- What expertise would they have?
- What would their priorities and concerns be?
- How would they approach problems?"""

    persona_data = complete_json(prompt=prompt, model=model, system=BOOTSTRAP_SYSTEM_PROMPT)
    return _repair_persona_data(persona_data, model)


def bootstrap_from_examples(
    examples: list[dict[str, str]],
    model: str = DEFAULT_MODEL,
) -> dict:
    """Infer persona from example conversations.

    Args:
        examples: List of {"user": ..., "assistant": ...} exchanges
        model: LLM model to use

    Returns:
        Dict with persona fields inferred from examples
    """
    examples_text = "\n\n".join(
        f"User: {ex['user']}\nAssistant: {ex['assistant']}" for ex in examples
    )

    prompt = f"""Analyze these example conversations and infer the persona of the assistant:

{examples_text}

Based on how the assistant communicates, create a persona specification that would reproduce this style."""

    persona_data = complete_json(prompt=prompt, model=model, system=BOOTSTRAP_SYSTEM_PROMPT)
    persona_data["examples"] = examples  # Keep original examples
    return _repair_persona_data(persona_data, model)
