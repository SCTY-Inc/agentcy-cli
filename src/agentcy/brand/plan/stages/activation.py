"""Activation stage - channel planning and execution."""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from agentcy.brand.core.llm import complete_json
from agentcy.brand.plan.stages.normalize import normalize_activation_result


class ChannelPlan(BaseModel):
    """Plan for a specific channel."""

    channel: str
    objective: str
    tactics: list[str] = Field(default_factory=list)
    content_types: list[str] = Field(default_factory=list)
    frequency: str | None = None
    budget_allocation: str | None = None


class CalendarItem(BaseModel):
    """Content calendar item."""

    date: str | None = None
    week: str | None = None
    channel: str
    content_type: str
    topic: str
    notes: str | None = None


class KPI(BaseModel):
    """Key performance indicator."""

    metric: str
    target: str
    channel: str | None = None


class ActivationResult(BaseModel):
    """Activation stage output."""

    channels: list[ChannelPlan] = Field(default_factory=list)
    calendar: list[CalendarItem] = Field(default_factory=list)
    kpis: list[KPI] = Field(default_factory=list)
    budget_allocation: dict[str, str] = Field(default_factory=dict)
    launch_checklist: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)


ACTIVATION_SYSTEM = """You are a senior marketing activation specialist.
Based on the creative, develop a detailed activation plan.

Output JSON with:
- channels: list of channel plans with channel, objective, tactics,
  content_types, frequency, budget_allocation
- calendar: content calendar items with week/date, channel, content_type, topic, notes
- kpis: list of KPIs with metric, target, channel
- budget_allocation: dict mapping channels to budget percentages
- launch_checklist: list of launch preparation items
- risks: list of potential risks and mitigations"""


def activation(
    creative_result: dict[str, Any] | None = None,
    strategy_result: dict[str, Any] | None = None,
    brief: str | None = None,
    brand: str | None = None,
) -> ActivationResult:
    """Execute the activation stage.

    Args:
        creative_result: Output from creative stage
        strategy_result: Output from strategy stage
        brief: Original brief (if no other inputs)
        brand: Optional brand name

    Returns:
        ActivationResult with channel plans and calendar
    """
    prompt_parts = []

    if creative_result:
        prompt_parts.append(f"Creative:\n{creative_result}")

    if strategy_result:
        prompt_parts.append(f"Strategy:\n{strategy_result}")

    if brief:
        prompt_parts.append(f"Brief: {brief}")

    if not prompt_parts:
        raise ValueError("At least one of creative_result, strategy_result, or brief required")

    if brand:
        prompt_parts.append(f"Brand: {brand}")

    prompt_parts.append("Develop a detailed activation and channel plan.")

    prompt = "\n\n".join(prompt_parts)

    default = ActivationResult().model_dump()

    result = complete_json(prompt=prompt, system=ACTIVATION_SYSTEM, default=default)

    return ActivationResult(**normalize_activation_result(result))
