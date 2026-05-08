"""Exa-based persona enrichment."""

from __future__ import annotations

from typing import TYPE_CHECKING

from agentcy.persona.clients import get_exa_client

if TYPE_CHECKING:
    from agentcy.persona.persona import Persona


def enrich_from_exa(persona: Persona, query: str | None = None) -> Persona:
    """Enrich persona with current information from Exa.

    Args:
        persona: The persona to enrich
        query: Search query (defaults to persona's dynamic.query or name)

    Returns:
        Enriched persona with updated context
    """
    exa = get_exa_client()

    # Determine search query
    search_query = query
    if not search_query and persona.dynamic:
        search_query = persona.dynamic.query
    if not search_query:
        search_query = persona.name

    # Search for person/entity
    results = exa.search(
        search_query,
        type="auto",
        category="people",
        num_results=5,
        use_autoprompt=True,
    )

    if not results.results:
        return persona

    # Get content from top results
    contents = exa.get_contents(
        [r.id for r in results.results[:3]],
        text={"max_characters": 2000},
        highlights={"num_sentences": 3},
    )

    # Extract and update context
    context_updates = {
        "sources": [r.url for r in results.results[:3]],
        "highlights": [],
        "enriched_at": _now_iso(),
    }

    for result in contents.results:
        if result.highlights:
            context_updates["highlights"].extend(result.highlights)

    # Merge into persona context
    persona.context.update(context_updates)

    return persona


def _now_iso() -> str:
    """Return current UTC time in ISO format."""
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()
