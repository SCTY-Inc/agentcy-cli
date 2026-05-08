"""Social media analysis plugin."""
from __future__ import annotations

from typing import Any

from agentcy.brand.core.llm import complete_json


def analyze_social(
    brand: str,
    platforms: list[str] | None = None,
) -> dict[str, Any]:
    """Analyze social media opportunities.

    Args:
        brand: Brand name or description
        platforms: Platforms to analyze

    Returns:
        Social media analysis and recommendations
    """
    platforms = platforms or ["twitter", "linkedin", "instagram"]

    prompt = f"""Analyze social media strategy for: {brand}
Platforms: {', '.join(platforms)}

Provide:
- platform_recommendations: recommendations per platform
- content_mix: suggested content types and ratios
- posting_schedule: optimal posting times and frequency
- engagement_tactics: ways to increase engagement
- hashtag_strategy: hashtag recommendations"""

    default = {
        "platform_recommendations": {},
        "content_mix": [],
        "posting_schedule": {},
        "engagement_tactics": [],
        "hashtag_strategy": [],
    }

    return complete_json(
        prompt=prompt,
        system="You are a social media strategist. Provide platform-specific recommendations.",
        default=default,
    )


def suggest_hashtags(topic: str, platform: str = "twitter", count: int = 10) -> list[str]:
    """Suggest hashtags for a topic.

    Args:
        topic: Content topic
        platform: Target platform
        count: Number of hashtags

    Returns:
        List of hashtag suggestions
    """
    result = complete_json(
        prompt=f"Suggest {count} {platform} hashtags for: {topic}",
        system="You are a social media expert. Output JSON with 'hashtags' array.",
        default={"hashtags": []},
    )

    return result.get("hashtags", [])[:count]
