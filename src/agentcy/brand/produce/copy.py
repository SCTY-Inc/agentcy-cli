"""Copy generation for social platforms."""
from __future__ import annotations

from typing import Any

from agentcy.brand.core.llm import complete_json


def generate_copy(
    topic: str,
    brand: str | None = None,
    platform: str = "twitter",
    hooks: list[dict[str, Any]] | None = None,
    learnings: list[str] | None = None,
    voice: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate copy for a topic.

    Args:
        topic: Content topic
        brand: Brand name
        platform: Target platform
        hooks: Hooks to incorporate
        learnings: Learnings from eval feedback
        voice: Voice guidelines

    Returns:
        Generated copy with variants
    """
    prompt_parts = [
        f"Write {platform} content about: {topic}",
    ]

    if brand:
        prompt_parts.append(f"Brand: {brand}")

    if voice:
        prompt_parts.append(f"Voice guidelines: {voice}")

    if hooks:
        hook_texts = [h.get("text", "") for h in hooks[:3]]
        prompt_parts.append(f"Use hook patterns like: {hook_texts}")

    if learnings:
        prompt_parts.append(f"Incorporate these learnings: {learnings[:5]}")

    prompt_parts.append(_get_platform_guidelines(platform))

    prompt = "\n\n".join(prompt_parts)

    default = {
        "main": "",
        "variants": [],
        "hashtags": [],
        "platform": platform,
    }

    return complete_json(
        prompt=prompt,
        system=f"You are a {platform} content expert. Write engaging, platform-native copy. Output JSON with main (string), variants (list of strings), hashtags (list).",
        default=default,
    )


def _get_platform_guidelines(platform: str) -> str:
    """Get platform-specific guidelines."""
    guidelines = {
        "twitter": "Max 280 characters. Punchy, direct. Use threads for longer content.",
        "linkedin": "Professional tone. 1-3 paragraphs. Can be longer and more detailed.",
        "instagram": "Visual-first. Use line breaks. 2200 char max. Include call-to-action.",
        "threads": "Conversational. Can be multi-part. Similar to Twitter but more casual.",
        "facebook": "Friendly tone. Can include links. Encourage engagement.",
    }
    return guidelines.get(platform, "Write engaging content.")


def generate_thread(
    topic: str,
    brand: str | None = None,
    num_tweets: int = 5,
    hooks: list[dict[str, Any]] | None = None,
) -> list[str]:
    """Generate a Twitter/X thread.

    Args:
        topic: Thread topic
        brand: Brand name
        num_tweets: Number of tweets in thread
        hooks: Hooks to incorporate

    Returns:
        List of tweet texts
    """
    prompt_parts = [
        f"Write a {num_tweets}-tweet thread about: {topic}",
    ]

    if brand:
        prompt_parts.append(f"Brand: {brand}")

    if hooks:
        hook_texts = [h.get("text", "") for h in hooks[:2]]
        prompt_parts.append(f"Start with a hook like: {hook_texts}")

    prompt_parts.append("""
Requirements:
- First tweet should hook the reader
- Each tweet max 280 characters
- Number tweets (1/, 2/, etc.)
- End with a call-to-action
- Output JSON with 'tweets' array""")

    prompt = "\n\n".join(prompt_parts)

    result = complete_json(
        prompt=prompt,
        system="You are a Twitter expert. Write viral thread content.",
        default={"tweets": []},
    )

    return result.get("tweets", [])


def generate_carousel_copy(
    topic: str,
    slides: int = 5,
    brand: str | None = None,
) -> list[dict[str, str]]:
    """Generate copy for an Instagram/LinkedIn carousel.

    Args:
        topic: Carousel topic
        slides: Number of slides
        brand: Brand name

    Returns:
        List of slide dicts with title and body
    """
    prompt = f"""Write copy for a {slides}-slide carousel about: {topic}
Brand: {brand or 'N/A'}

Output JSON with 'slides' array, each with:
- title: short punchy title (5-8 words max)
- body: supporting text (2-3 sentences)
- cta: optional call-to-action for last slide"""

    result = complete_json(
        prompt=prompt,
        system="You are a carousel content expert. Write scannable, value-packed slide copy.",
        default={"slides": []},
    )

    return result.get("slides", [])
