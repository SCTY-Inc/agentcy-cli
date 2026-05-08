"""SEO analysis plugin."""
from __future__ import annotations

from typing import Any

from agentcy.brand.core.llm import complete_json


def analyze_seo(
    topic: str,
    competitors: list[str] | None = None,
) -> dict[str, Any]:
    """Analyze SEO opportunities for a topic.

    Args:
        topic: Main topic or keyword
        competitors: Optional competitor domains

    Returns:
        SEO analysis with keywords and recommendations
    """
    prompt_parts = [f"Analyze SEO opportunities for: {topic}"]

    if competitors:
        prompt_parts.append(f"Competitors to consider: {', '.join(competitors)}")

    prompt_parts.append("""Provide:
- primary_keywords: list of target keywords
- secondary_keywords: list of supporting keywords
- content_gaps: opportunities competitors are missing
- recommendations: SEO strategy recommendations
- meta_suggestions: title and description suggestions""")

    prompt = "\n".join(prompt_parts)

    default = {
        "primary_keywords": [],
        "secondary_keywords": [],
        "content_gaps": [],
        "recommendations": [],
        "meta_suggestions": {},
    }

    return complete_json(
        prompt=prompt,
        system="You are an SEO specialist. Provide actionable keyword and content recommendations.",
        default=default,
    )


def suggest_keywords(topic: str, count: int = 10) -> list[str]:
    """Suggest keywords for a topic.

    Args:
        topic: Main topic
        count: Number of keywords to suggest

    Returns:
        List of keyword suggestions
    """
    result = complete_json(
        prompt=f"Suggest {count} SEO keywords for: {topic}",
        system="You are an SEO specialist. Output JSON with 'keywords' array.",
        default={"keywords": []},
    )

    return result.get("keywords", [])[:count]
