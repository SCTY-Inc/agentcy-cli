"""Thin canonical brief.v1 import adapter for agentcy-echo."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")


class BriefWriter(BaseModel):
    repo: Literal["brand-os"] = "brand-os"
    module: Literal["agentcy-compass"] = "agentcy-compass"


class BriefSignal(BaseModel):
    source: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)


class BriefStrategy(BaseModel):
    angle: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    platforms: list[str] = Field(min_length=1)


class BriefPolicy(BaseModel):
    verdict: Literal["approved", "escalate", "deny"]
    confidence: float = Field(ge=0, le=1)
    notes: list[str] = Field(default_factory=list)


class BriefDeliverable(BaseModel):
    kind: str = Field(min_length=1)
    channel: str = Field(min_length=1)
    notes: str | None = None


class BriefCreative(BaseModel):
    headline: str = Field(min_length=1)
    copy_text: str = Field(alias="copy", min_length=1)
    tone_notes: list[str] = Field(min_length=1)
    deliverables: list[BriefDeliverable] = Field(default_factory=list)


class BriefLineage(BaseModel):
    source_voice_pack_id: str | None = None
    campaign_id: str | None = None
    signal_id: str | None = None

    @field_validator("source_voice_pack_id", "campaign_id", "signal_id")
    @classmethod
    def _validate_optional_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not ID_PATTERN.match(value):
            raise ValueError("lineage IDs must match canonical pattern")
        return value


class BriefV1(BaseModel):
    artifact_type: Literal["brief.v1"]
    schema_version: Literal["v1"]
    brief_id: str
    brand_id: str
    voice_pack_id: str
    writer: BriefWriter
    objective: str = Field(min_length=1)
    signal: BriefSignal
    strategy: BriefStrategy
    policy: BriefPolicy
    creative: BriefCreative
    lineage: BriefLineage | None = None

    @field_validator("brief_id", "brand_id", "voice_pack_id")
    @classmethod
    def _validate_ids(cls, value: str) -> str:
        if not ID_PATTERN.match(value):
            raise ValueError("IDs must match canonical pattern")
        return value

    @model_validator(mode="after")
    def _validate_lineage(self) -> "BriefV1":
        if self.lineage and self.lineage.source_voice_pack_id is not None:
            if self.lineage.source_voice_pack_id != self.voice_pack_id:
                raise ValueError("lineage.source_voice_pack_id must equal voice_pack_id")
        return self


class ImportedBrief(BaseModel):
    brief: BriefV1
    requirement: str
    frozen_input: dict
    lineage: dict



def _clean_lines(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(normalized)
    return cleaned



def _derive_requirement(brief: BriefV1) -> str:
    platforms = ", ".join(brief.strategy.platforms)
    deliverable_channels = ", ".join(
        _clean_lines([item.channel for item in brief.creative.deliverables])
    )
    parts = _clean_lines(
        [
            f"Objective: {brief.objective}",
            f"Signal source: {brief.signal.source}",
            f"Signal summary: {brief.signal.summary}",
            f"Strategy angle: {brief.strategy.angle}",
            f"Call to action: {brief.strategy.cta}",
            f"Primary platforms: {platforms}" if platforms else "",
            f"Creative headline: {brief.creative.headline}",
            f"Creative copy seed: {brief.creative.copy_text}",
            f"Deliverable channels: {deliverable_channels}" if deliverable_channels else "",
            "Model plausible public reaction, likely discussion themes, and platform-specific response dynamics.",
        ]
    )
    return "\n".join(parts)



def _build_frozen_input(brief: BriefV1) -> dict:
    return {
        "artifact_type": brief.artifact_type,
        "schema_version": brief.schema_version,
        "brief_id": brief.brief_id,
        "brand_id": brief.brand_id,
        "voice_pack_id": brief.voice_pack_id,
        "objective": brief.objective,
        "signal": brief.signal.model_dump(exclude_none=True),
        "strategy": brief.strategy.model_dump(exclude_none=True),
        "policy": brief.policy.model_dump(exclude_none=True),
        "creative": brief.creative.model_dump(exclude_none=True),
        "lineage": {
            "source_brief_id": brief.brief_id,
            "source_voice_pack_id": (
                brief.lineage.source_voice_pack_id if brief.lineage else brief.voice_pack_id
            ),
            "campaign_id": brief.lineage.campaign_id if brief.lineage else None,
            "signal_id": brief.lineage.signal_id if brief.lineage else None,
        },
    }



def _build_manifest_lineage(brief: BriefV1) -> dict:
    return {
        "brief_id": brief.brief_id,
        "brand_id": brief.brand_id,
        "source_voice_pack_id": (
            brief.lineage.source_voice_pack_id if brief.lineage else brief.voice_pack_id
        ),
        "campaign_id": brief.lineage.campaign_id if brief.lineage else None,
        "signal_id": brief.lineage.signal_id if brief.lineage else None,
    }



def import_brief_v1(path: str | Path) -> ImportedBrief:
    brief_path = Path(path).expanduser().resolve()
    try:
        payload = json.loads(brief_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid brief.v1 JSON: {exc}") from exc

    try:
        brief = BriefV1.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid brief.v1 payload: {exc}") from exc

    return ImportedBrief(
        brief=brief,
        requirement=_derive_requirement(brief),
        frozen_input=_build_frozen_input(brief),
        lineage=_build_manifest_lineage(brief),
    )
