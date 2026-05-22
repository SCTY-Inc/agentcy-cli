"""Hook extraction from viral content."""
from __future__ import annotations

from typing import Any

from agentcy_briefs.core.llm import complete_json


HOOK_SYSTEM = """You are an expert at analyzing viral content patterns.
Extract the "hooks" - the specific elements that make content engaging.

For each hook, identify:
- type: opener, closer, pattern, structure, emotional, curiosity, authority
- text: the actual text or pattern
- explanation: why it works

Output JSON array of hooks."""


def extract_hooks(
    posts: list[dict[str, Any]],
    brand: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Extract hooks from viral posts.

    Args:
        posts: List of outlier/viral posts
        brand: Optional brand name for context
        limit: Max hooks to extract

    Returns:
        List of extracted hooks
    """
    if not posts:
        return []

    # Take top posts by outlier score
    sorted_posts = sorted(
        posts,
        key=lambda x: x.get("outlier_score", x.get("engagement_score", 0)),
        reverse=True,
    )[:limit]

    prompt_parts = ["Analyze these viral posts and extract the hooks that made them successful."]

    if brand:
        prompt_parts.append(f"Context: These are from {brand}'s competitors or industry.")

    prompt_parts.append("\n## Posts to Analyze")

    for i, post in enumerate(sorted_posts, 1):
        text = post.get("text", "")[:500]  # Limit text length
        score = post.get("outlier_score", 0)
        prompt_parts.append(f"\n### Post {i} (Score: {score:.1f}x median)")
        prompt_parts.append(text)

    prompt_parts.append("\nExtract hooks as JSON array.")

    prompt = "\n".join(prompt_parts)

    default = []
    hooks = complete_json(prompt=prompt, system=HOOK_SYSTEM, default=default)

    if isinstance(hooks, dict):
        hooks = hooks.get("hooks", [])

    for hook in hooks:
        hook["source"] = "extracted"
        hook["brand"] = brand

    return hooks
