"""Persona enrichment via external data sources."""
from __future__ import annotations

from typing import Any

from brand_os.persona.crud import load_persona, save_persona


def enrich_persona(name: str, source: str = "exa") -> dict[str, Any]:
    """Enrich a persona with external data.

    Args:
        name: Persona name
        source: Data source ("exa" for Exa people search)

    Returns:
        Updated persona dictionary
    """
    persona = load_persona(name)

    if source == "exa":
        enrichment = _enrich_with_exa(persona)
    else:
        raise ValueError(f"Unknown enrichment source: {source}")

    # Merge enrichment into persona context
    context = persona.get("context", {})
    context["enrichment"] = enrichment
    context["enrichment_source"] = source
    persona["context"] = context

    save_persona(name, persona)
    return persona


def _enrich_with_exa(persona: dict[str, Any]) -> dict[str, Any]:
    """Enrich persona using Exa people search.

    Requires: exa-py optional dependency
    """
    try:
        from exa_py import Exa
    except ImportError:
        raise ImportError("exa-py required for Exa enrichment. Install with: pip install agentcy-compass[persona]")

    import os
    api_key = os.getenv("EXA_API_KEY")
    if not api_key:
        raise ValueError("EXA_API_KEY environment variable required")

    exa = Exa(api_key=api_key)

    # Search for relevant information about the persona
    persona_name = persona.get("name", "")
    description = persona.get("description", "")
    query = f"{persona_name} {description}"

    results = exa.search_and_contents(
        query=query,
        type="auto",
        num_results=5,
        text=True,
    )

    enrichment = {
        "sources": [],
        "insights": [],
    }

    for result in results.results:
        enrichment["sources"].append({
            "title": result.title,
            "url": result.url,
            "excerpt": result.text[:500] if result.text else None,
        })

    return enrichment
