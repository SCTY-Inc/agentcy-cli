"""Canonical brief.v1 model and thin planning adapter."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from agentcy.brand.core.brands import load_brand_profile

ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")


class VoicePackWriter(BaseModel):
    repo: Literal["cli-prsna"] = "cli-prsna"
    module: Literal["agentcy-vox"] = "agentcy-vox"


class VoicePackVoice(BaseModel):
    tone: list[str]
    style: list[str]
    audience: list[str]


class VoicePackLexicon(BaseModel):
    preferred: list[str] = Field(default_factory=list)
    avoid: list[str] = Field(default_factory=list)


class VoicePackConstraints(BaseModel):
    dos: list[str]
    donts: list[str]
    lexicon: VoicePackLexicon | None = None


class VoicePackExample(BaseModel):
    label: str
    text: str


class VoicePackSource(BaseModel):
    persona_id: str | None = None
    persona_version: str | None = None
    notes: str | None = None


class VoicePackV1(BaseModel):
    artifact_type: Literal["voice_pack.v1"] = "voice_pack.v1"
    schema_version: Literal["v1"] = "v1"
    voice_pack_id: str
    brand_id: str
    writer: VoicePackWriter
    name: str
    summary: str
    traits: list[str] = Field(default_factory=list)
    voice: VoicePackVoice
    constraints: VoicePackConstraints
    examples: list[VoicePackExample] = Field(default_factory=list)
    source: VoicePackSource | None = None

    @field_validator("voice_pack_id", "brand_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        if not ID_PATTERN.match(value):
            raise ValueError("IDs must match canonical pattern")
        return value


class BriefWriter(BaseModel):
    repo: Literal["brand-os"] = "brand-os"
    module: Literal["agentcy-compass"] = "agentcy-compass"


class BriefSignal(BaseModel):
    source: str
    summary: str
    evidence: list[str] = Field(default_factory=list)


class BriefStrategy(BaseModel):
    angle: str
    cta: str
    platforms: list[str]


class BriefPolicy(BaseModel):
    verdict: Literal["approved", "escalate", "deny"]
    confidence: float = Field(ge=0, le=1)
    notes: list[str] = Field(default_factory=list)


class BriefDeliverable(BaseModel):
    kind: str
    channel: str
    notes: str | None = None


class BriefCreative(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    headline: str
    copy_text: str = Field(alias="copy")
    tone_notes: list[str]
    deliverables: list[BriefDeliverable] = Field(default_factory=list)


class BriefLineage(BaseModel):
    source_voice_pack_id: str | None = None
    campaign_id: str | None = None
    signal_id: str | None = None

    @field_validator("source_voice_pack_id", "campaign_id", "signal_id")
    @classmethod
    def validate_optional_ids(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not ID_PATTERN.match(value):
            raise ValueError("lineage IDs must match canonical pattern")
        return value


class BriefV1(BaseModel):
    artifact_type: Literal["brief.v1"] = "brief.v1"
    schema_version: Literal["v1"] = "v1"
    brief_id: str
    brand_id: str
    voice_pack_id: str
    writer: BriefWriter = Field(default_factory=BriefWriter)
    objective: str
    signal: BriefSignal
    strategy: BriefStrategy
    policy: BriefPolicy
    creative: BriefCreative
    lineage: BriefLineage | None = None

    @field_validator("brief_id", "brand_id", "voice_pack_id")
    @classmethod
    def validate_ids(cls, value: str) -> str:
        if not ID_PATTERN.match(value):
            raise ValueError("IDs must match canonical pattern")
        return value

    @field_validator("lineage")
    @classmethod
    def validate_lineage_voice_pack(cls, value: BriefLineage | None, info) -> BriefLineage | None:
        if value and value.source_voice_pack_id is not None:
            voice_pack_id = info.data.get("voice_pack_id")
            if voice_pack_id and value.source_voice_pack_id != voice_pack_id:
                raise ValueError("lineage.source_voice_pack_id must equal voice_pack_id")
        return value


def slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    slug = slug.replace("-", ".")
    return slug or "brand"


def default_brand_id(brand: str | None) -> str:
    return f"{slugify(brand or 'brand')}.brand.core"


def default_brief_id(brand: str | None, campaign_id: str) -> str:
    return f"{slugify(brand or 'brand')}.brief.{campaign_id}"


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        normalized = item.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered


def _voice_pack_tone_notes(voice_pack: VoicePackV1 | None) -> list[str]:
    if voice_pack is None:
        return []

    notes = [
        *voice_pack.traits,
        *voice_pack.voice.tone,
        *voice_pack.voice.style,
        *voice_pack.constraints.dos,
        *(f"avoid {item}" for item in voice_pack.constraints.donts),
    ]
    return _dedupe(notes)


def _compact_source_refs(research_result: dict) -> list[str]:
    refs: list[str] = []
    for item in research_result.get("sources", []):
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        snippet = str(item.get("snippet") or "").strip()
        if title and url:
            refs.append(f"{title} ({url})")
        elif title:
            refs.append(title)
        elif url:
            refs.append(url)
        if snippet:
            refs.append(snippet)
    return _dedupe(refs)


def _audience_lines(strategy_result: dict) -> list[str]:
    lines: list[str] = []
    audience = strategy_result.get("target_audience")
    audience_items = [audience] if isinstance(audience, dict) else []
    audience_items.extend(
        item
        for item in strategy_result.get("audience", [])
        if isinstance(item, dict)
    )

    for item in audience_items:
        name = str(item.get("name") or "").strip()
        description = str(item.get("description") or item.get("demographics") or "").strip()
        if name and description:
            lines.append(f"{name}: {description}")
        elif name:
            lines.append(name)
        elif description:
            lines.append(description)
        lines.extend(
            str(value).strip()
            for value in item.get("pain_points", [])
            if str(value).strip()
        )
        lines.extend(
            str(value).strip()
            for value in item.get("motivations", [])
            if str(value).strip()
        )
    return _dedupe(lines)


def _deliverable_notes(
    objective: str | None,
    messaging_pillars: list[str],
    proof_points: list[str],
    audience_lines: list[str],
) -> str | None:
    notes = _dedupe([
        objective or "",
        *(f"pillar: {item}" for item in messaging_pillars[:2]),
        *(f"proof: {item}" for item in proof_points[:1]),
        *(f"audience: {item}" for item in audience_lines[:1]),
    ])
    if not notes:
        return None
    return " | ".join(notes)


def load_voice_pack_v1(path: Path) -> VoicePackV1:
    return VoicePackV1.model_validate_json(path.read_text())


def build_brief_v1(
    *,
    brief: str,
    brand: str | None,
    voice_pack_id: str | None,
    campaign_id: str,
    research_result: dict,
    strategy_result: dict,
    creative_result: dict,
    activation_result: dict,
    voice_pack: VoicePackV1 | None = None,
    brand_id: str | None = None,
    signal_source: str | None = None,
    signal_id: str | None = None,
    policy_verdict: Literal["approved", "escalate", "deny"] = "escalate",
    policy_confidence: float = 0.5,
) -> BriefV1:
    profile = load_brand_profile(brand) if brand else None

    resolved_voice_pack_id = voice_pack.voice_pack_id if voice_pack else voice_pack_id
    if not resolved_voice_pack_id:
        raise ValueError("voice_pack_id or voice_pack is required")
    if voice_pack and voice_pack_id and voice_pack.voice_pack_id != voice_pack_id:
        raise ValueError("voice_pack.voice_pack_id must equal voice_pack_id")

    insights = [item for item in research_result.get("insights", []) if item]
    assumptions = [item for item in research_result.get("assumptions", []) if item]
    source_refs = _compact_source_refs(research_result)
    messaging_pillars = [item for item in strategy_result.get("messaging_pillars", []) if item]
    proof_points = [item for item in strategy_result.get("proof_points", []) if item]
    strategy_risks = [item for item in strategy_result.get("risks", []) if item]
    audience_lines = _audience_lines(strategy_result)
    evidence = _dedupe(insights + assumptions + proof_points + source_refs)[:5]

    channels = activation_result.get("channels", [])
    platforms = [item.get("channel") for item in channels if item.get("channel")]
    if not platforms and profile and profile.platforms:
        platforms = list(profile.platforms.keys())
    platforms = list(dict.fromkeys(platforms)) or ["email"]

    headlines = [
        item.get("text")
        for item in creative_result.get("headlines", [])
        if item.get("text")
    ]
    body_copy = [item for item in creative_result.get("body_copy", []) if item]
    tone_notes = [item for item in creative_result.get("tone_notes", []) if item]
    if not tone_notes and profile and profile.identity.voice.tone:
        tone_notes = [profile.identity.voice.tone]
    tone_notes = _dedupe(
        tone_notes + _voice_pack_tone_notes(voice_pack)
    ) or ["clear"]

    deliverables = [
        BriefDeliverable(
            kind=(
                item.get("content_types", ["campaign"])[0]
                if item.get("content_types")
                else "campaign"
            ),
            channel=item["channel"],
            notes=_deliverable_notes(
                item.get("objective"),
                messaging_pillars,
                proof_points,
                audience_lines,
            ),
        )
        for item in channels
        if item.get("channel")
    ]

    sources = research_result.get("sources") or [{}]
    first_source = sources[0] if isinstance(sources[0], dict) else {}

    signal = BriefSignal(
        source=(
            signal_source
            or first_source.get("title")
            or "planning-input"
        ),
        summary=insights[0] if insights else brief,
        evidence=evidence,
    )
    angle_parts = _dedupe(
        [
            strategy_result.get("positioning") or "",
            strategy_result.get("value_proposition") or "",
            *(f"Audience: {item}" for item in audience_lines[:1]),
            *(f"Pillar: {item}" for item in messaging_pillars[:1]),
        ]
    )
    cta_options = [item for item in creative_result.get("ctas", []) if item]
    cta_options.extend(f"Support this with {item}." for item in proof_points[:1])
    built = BriefV1(
        brief_id=default_brief_id(brand, campaign_id),
        brand_id=(
            brand_id
            or (voice_pack.brand_id if voice_pack else None)
            or default_brand_id(brand)
        ),
        voice_pack_id=resolved_voice_pack_id,
        objective=brief,
        signal=signal,
        strategy=BriefStrategy(
            angle=" | ".join(angle_parts) if angle_parts else brief,
            cta=cta_options[0] if cta_options else "Review the plan and choose the next action.",
            platforms=platforms,
        ),
        policy=BriefPolicy(
            verdict=policy_verdict,
            confidence=policy_confidence,
            notes=_dedupe(activation_result.get("risks", []) + strategy_risks),
        ),
        creative=BriefCreative(
            headline=headlines[0] if headlines else brief,
            copy=(
                body_copy[0]
                if body_copy
                else " ".join(
                    _dedupe(
                        [
                            strategy_result.get("value_proposition") or "",
                            *proof_points[:1],
                        ]
                    )
                )
                or brief
            ),
            tone_notes=tone_notes,
            deliverables=deliverables,
        ),
        lineage=BriefLineage(
            source_voice_pack_id=resolved_voice_pack_id,
            campaign_id=campaign_id,
            signal_id=signal_id,
        ),
    )
    return built


def write_brief_v1(path: Path, brief: BriefV1) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            brief.model_dump(exclude_none=True, by_alias=True),
            indent=2,
            ensure_ascii=False,
        )
    )
