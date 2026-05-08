"""Hook extraction from viral content."""
from __future__ import annotations

from typing import Any

from agentcy.brand.core.llm import complete_json

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

    # Build prompt
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

    # Ensure it's a list
    if isinstance(hooks, dict):
        hooks = hooks.get("hooks", [])

    # Add source info
    for hook in hooks:
        hook["source"] = "extracted"
        hook["brand"] = brand

    return hooks


def categorize_hook(hook_text: str) -> str:
    """Categorize a hook by type.

    Args:
        hook_text: The hook text

    Returns:
        Hook category
    """
    text_lower = hook_text.lower()

    # Pattern matching for common hook types
    if any(word in text_lower for word in ["why", "how", "what if", "secret", "truth"]):
        return "curiosity"
    elif any(word in text_lower for word in ["you", "your", "you're"]):
        return "direct_address"
    elif any(word in text_lower for word in ["never", "always", "everyone", "nobody"]):
        return "absolute"
    elif any(word in text_lower for word in ["mistake", "wrong", "fail", "stop"]):
        return "fear"
    elif any(word in text_lower for word in ["easy", "simple", "quick", "fast"]):
        return "ease"
    elif text_lower.startswith(("i ", "my ", "we ")):
        return "personal"
    elif "?" in hook_text:
        return "question"
    elif any(char.isdigit() for char in hook_text[:10]):
        return "number"
    else:
        return "other"


def build_hook_bank(hooks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Organize hooks into a categorized bank.

    Args:
        hooks: List of hooks

    Returns:
        Dict mapping categories to hooks
    """
    bank: dict[str, list[dict[str, Any]]] = {}

    for hook in hooks:
        category = hook.get("type") or categorize_hook(hook.get("text", ""))

        if category not in bank:
            bank[category] = []
        bank[category].append(hook)

    return bank


def suggest_hooks(
    topic: str,
    brand: str | None = None,
    hook_bank: dict[str, list[dict[str, Any]]] | None = None,
) -> list[str]:
    """Suggest hooks for a topic.

    Args:
        topic: Content topic
        brand: Optional brand name
        hook_bank: Optional hook bank to draw from

    Returns:
        List of suggested hook texts
    """
    prompt_parts = [f"Suggest 5 engaging hooks for content about: {topic}"]

    if brand:
        prompt_parts.append(f"Brand voice: {brand}")

    if hook_bank:
        prompt_parts.append("\nUse these hook patterns as inspiration:")
        for category, hooks in list(hook_bank.items())[:3]:
            prompt_parts.append(f"- {category}: {hooks[0].get('text', '')[:100]}")

    prompt = "\n".join(prompt_parts)

    result = complete_json(
        prompt=prompt,
        system="Generate engaging content hooks. Output JSON array of hook strings.",
        default=["Hook 1", "Hook 2", "Hook 3", "Hook 4", "Hook 5"],
    )

    if isinstance(result, dict):
        result = result.get("hooks", [])

    return result
