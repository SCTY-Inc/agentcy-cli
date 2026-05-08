from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field


class Signal(BaseModel):
    title: str
    snippet: str | None = None
    url: str | None = None
    source: str | None = None
    source_type: str | None = None
    published_at: date | None = None
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class SignalQuery(BaseModel):
    query: str
    scope: str | None = None
    keywords: list[str] = Field(default_factory=list)
    stop_phrases: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


def filter_signals(
    signals: list[Signal],
    keywords: list[str] | None = None,
    stop_phrases: list[str] | None = None,
) -> list[Signal]:
    if not signals:
        return []

    keyword_set = {kw.lower() for kw in (keywords or []) if kw}
    stop_set = {phrase.lower() for phrase in (stop_phrases or []) if phrase}

    filtered: list[Signal] = []
    for signal in signals:
        text = " ".join(filter(None, [signal.title, signal.snippet])).lower()
        if stop_set and any(phrase in text for phrase in stop_set):
            continue
        if keyword_set and not any(keyword in text for keyword in keyword_set):
            continue
        filtered.append(signal)
    return filtered
