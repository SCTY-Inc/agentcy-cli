"""Research stage - market research and analysis.

This stage stays repo-local to brand-os and selectively re-homes only durable
cli-agency research concepts that can strengthen the brief.v1 seam.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentcy.brand.core.llm import complete_json
from agentcy.brand.plan.stages.normalize import normalize_research_result


class Competitor(BaseModel):
    """Competitor analysis."""

    name: str
    positioning: str
    strengths: list[str] = Field(default_factory=list)
    weaknesses: list[str] = Field(default_factory=list)


class Source(BaseModel):
    """Research source."""

    url: str
    title: str
    snippet: str | None = None


class ResearchResult(BaseModel):
    """Research stage output."""

    brief: str
    insights: list[str] = Field(default_factory=list)
    competitors: list[Competitor] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    market_size: str | None = None
    trends: list[str] = Field(default_factory=list)


RESEARCH_SYSTEM = """You are a senior market research analyst.
Analyze the brief and provide comprehensive research insights.

Output JSON with:
- brief: the original brief
- insights: list of 5-7 key market insights
- competitors: list of competitors with name, positioning, strengths, weaknesses
- sources: list of relevant sources (can be hypothetical but realistic)
- assumptions: list of assumptions made
- market_size: estimated market size if relevant
- trends: list of relevant market trends

Focus on durable planning concepts that strengthen a canonical brief.v1 seam:
concise insights, source-backed context, explicit assumptions, and narrowed
competitor framing. Do not drift into runtime, plugin, MCP, or execution logic."""

def research(
    brief: str,
    brand: str | None = None,
    context: dict[str, Any] | None = None,
) -> ResearchResult:
    """Execute the research stage.

    Args:
        brief: Campaign brief or research question
        brand: Optional brand name for context
        context: Optional additional context

    Returns:
        ResearchResult with insights and analysis
    """
    prompt_parts = [f"Research brief: {brief}"]

    if brand:
        prompt_parts.append(f"Brand: {brand}")

    if context:
        prompt_parts.append(f"Additional context: {context}")

    prompt_parts.append(
        "Provide comprehensive market research and competitor analysis "
        "with brief.v1-ready context. Prioritize concise insights, "
        "assumptions that should remain explicit, narrowed competitor "
        "context, and compact source provenance."
    )

    prompt = "\n\n".join(prompt_parts)

    default = ResearchResult(brief=brief).model_dump()

    result = complete_json(prompt=prompt, system=RESEARCH_SYSTEM, default=default)

    return ResearchResult(**normalize_research_result(result, brief=brief))
