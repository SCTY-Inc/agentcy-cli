"""Strategy stage - positioning and planning.

This stage keeps brand-os as the canonical brief.v1 writer while selectively
re-homing only the smallest durable strategy concepts from cli-agency:
positioning, audience framing, messaging pillars, proof points, and risks.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentcy.brand.core.llm import complete_json
from agentcy.brand.plan.stages.normalize import normalize_strategy_result


class AudienceSegment(BaseModel):
    """Target audience segment."""

    name: str
    description: str
    pain_points: list[str] = Field(default_factory=list)
    motivations: list[str] = Field(default_factory=list)


class Pillar(BaseModel):
    """Strategic content pillar."""

    name: str
    description: str
    topics: list[str] = Field(default_factory=list)


class StrategyResult(BaseModel):
    """Strategy stage output.

    The added target_audience, messaging_pillars, proof_points, and risks fields
    are a selective re-home of cli-agency strategy concepts, not a second brief
    writer or a broader runtime merge.
    """

    positioning: str
    value_proposition: str | None = None
    audience: list[AudienceSegment] = Field(default_factory=list)
    target_audience: AudienceSegment | None = None
    pillars: list[Pillar] = Field(default_factory=list)
    messaging_pillars: list[str] = Field(default_factory=list)
    proof_points: list[str] = Field(default_factory=list)
    differentiators: list[str] = Field(default_factory=list)
    messaging_guidelines: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    budget_recommendation: str | None = None
    timeline: str | None = None


STRATEGY_SYSTEM = """You are a senior brand strategist.
Based on the research, develop a comprehensive strategy.

Output JSON with:
- positioning: clear positioning statement
- value_proposition: core value proposition
- audience: list of audience segments with name, description, pain_points, motivations
- target_audience: one primary audience frame with name, description, pain_points, motivations
- pillars: content pillars with name, description, topics
- messaging_pillars: 3-5 concise messaging pillars
- proof_points: evidence or claims that support the positioning
- differentiators: list of key differentiators
- messaging_guidelines: list of messaging do's and don'ts
- risks: strategic risks, objections, or caveats to avoid
- budget_recommendation: suggested budget approach
- timeline: recommended timeline

Focus on durable planning concepts that strengthen the eventual brief.v1 output.
Do not invent runtime, plugin, MCP, or execution ownership."""

def strategy(
    research_result: dict[str, Any] | None = None,
    brief: str | None = None,
    brand: str | None = None,
) -> StrategyResult:
    """Execute the strategy stage.

    Args:
        research_result: Output from research stage
        brief: Original brief (if no research result)
        brand: Optional brand name

    Returns:
        StrategyResult with positioning and plan
    """
    prompt_parts = []

    if research_result:
        prompt_parts.append(f"Research findings:\n{research_result}")
    elif brief:
        prompt_parts.append(f"Brief: {brief}")
    else:
        raise ValueError("Either research_result or brief required")

    if brand:
        prompt_parts.append(f"Brand: {brand}")

    prompt_parts.append(
        "Develop a comprehensive brand/marketing strategy with durable planning outputs. "
        "Prioritize positioning, audience framing, messaging pillars, proof points, and risks "
        "that can strengthen a canonical brief.v1 artifact."
    )

    prompt = "\n\n".join(prompt_parts)

    default = StrategyResult(positioning="").model_dump()

    result = complete_json(prompt=prompt, system=STRATEGY_SYSTEM, default=default)

    return StrategyResult(**normalize_strategy_result(result))
