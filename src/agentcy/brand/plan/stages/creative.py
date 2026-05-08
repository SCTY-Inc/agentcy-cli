"""Creative stage - copy and asset generation."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentcy.brand.core.llm import complete_json
from agentcy.brand.plan.stages.normalize import normalize_creative_result


class Headline(BaseModel):
    """Creative headline."""

    text: str
    variant: str | None = None  # e.g., "emotional", "benefit-driven"


class Asset(BaseModel):
    """Creative asset specification."""

    type: str  # e.g., "image", "video", "infographic"
    description: str
    dimensions: str | None = None
    platform: str | None = None


class CreativeResult(BaseModel):
    """Creative stage output."""

    headlines: list[Headline] = Field(default_factory=list)
    body_copy: list[str] = Field(default_factory=list)
    ctas: list[str] = Field(default_factory=list)
    taglines: list[str] = Field(default_factory=list)
    assets: list[Asset] = Field(default_factory=list)
    tone_notes: list[str] = Field(default_factory=list)


CREATIVE_SYSTEM = """You are a senior creative director.
Based on the strategy, develop creative concepts and copy.

Output JSON with:
- headlines: list of headlines with text and variant type
- body_copy: list of body copy variations
- ctas: list of call-to-action options
- taglines: list of tagline options
- assets: list of asset specifications with type, description, dimensions, platform
- tone_notes: notes on tone and style"""


def creative(
    strategy_result: dict[str, Any] | None = None,
    brief: str | None = None,
    brand: str | None = None,
) -> CreativeResult:
    """Execute the creative stage.

    Args:
        strategy_result: Output from strategy stage
        brief: Original brief (if no strategy result)
        brand: Optional brand name

    Returns:
        CreativeResult with copy and asset specs
    """
    prompt_parts = []

    if strategy_result:
        prompt_parts.append(f"Strategy:\n{strategy_result}")
    elif brief:
        prompt_parts.append(f"Brief: {brief}")
    else:
        raise ValueError("Either strategy_result or brief required")

    if brand:
        prompt_parts.append(f"Brand: {brand}")

    prompt_parts.append("Develop creative concepts, headlines, and copy.")

    prompt = "\n\n".join(prompt_parts)

    default = CreativeResult().model_dump()

    result = complete_json(prompt=prompt, system=CREATIVE_SYSTEM, default=default)

    return CreativeResult(**normalize_creative_result(result))
