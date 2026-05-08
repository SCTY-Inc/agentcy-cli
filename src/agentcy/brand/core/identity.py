from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class Example(BaseModel):
    user: str
    assistant: str


class Voice(BaseModel):
    tone: str | None = None
    vocabulary: str | None = None
    patterns: list[str] = Field(default_factory=list)
    writing_system: str | None = None
    style: str | None = None
    rules: list[str] = Field(default_factory=list)
    avoid_phrases: list[str] = Field(default_factory=list)
    frames: list[str] = Field(default_factory=list)


class Identity(BaseModel):
    name: str
    description: str | None = None
    traits: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)
    examples: list[Example] = Field(default_factory=list)
    voice: Voice = Field(default_factory=Voice)
    metadata: dict[str, Any] = Field(default_factory=dict)


class Visual(BaseModel):
    palette: dict[str, Any] | None = None
    typography: dict[str, Any] | None = None
    logo: dict[str, Any] | None = None
    prompt_override: str | None = None
    raw: dict[str, Any] | None = None


class BrandProfile(BaseModel):
    identity: Identity
    visual: Visual | None = None
    platforms: dict[str, Any] | None = None
    handles: dict[str, Any] | None = None
    rubric: dict[str, Any] | None = None
    keywords: list[str] | None = None
    competitors: list[str] | None = None
    stop_phrases: list[str] | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
