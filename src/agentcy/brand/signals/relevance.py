"""Signal relevance filtering."""
from __future__ import annotations

from typing import Any


def score_relevance(
    signal: dict[str, Any],
    keywords: list[str],
    competitors: list[str] | None = None,
    stop_phrases: list[str] | None = None,
) -> float:
    """Score a signal's relevance.

    Args:
        signal: Signal dict with headline/text
        keywords: Keywords to match
        competitors: Competitor names to match
        stop_phrases: Phrases that reduce relevance

    Returns:
        Relevance score 0-1
    """
    text = _get_signal_text(signal).lower()

    if not text:
        return 0.0

    score = 0.0
    max_score = 0.0

    # Keyword matches (primary)
    max_score += len(keywords)
    for keyword in keywords:
        if keyword.lower() in text:
            score += 1.0

    # Competitor matches (secondary)
    if competitors:
        max_score += len(competitors) * 0.5
        for competitor in competitors:
            if competitor.lower() in text:
                score += 0.5

    # Stop phrase penalties
    if stop_phrases:
        for phrase in stop_phrases:
            if phrase.lower() in text:
                score -= 0.3


    if max_score > 0:
        normalized = score / max_score
        return max(0.0, min(1.0, normalized))

    return 0.0


def filter_signals(
    signals: list[dict[str, Any]],
    keywords: list[str] | None = None,
    competitors: list[str] | None = None,
    stop_phrases: list[str] | None = None,
    min_score: float = 0.1,
) -> list[dict[str, Any]]:
    """Filter signals by relevance.

    Args:
        signals: List of signals
        keywords: Keywords to match
        competitors: Competitor names
        stop_phrases: Phrases to penalize
        min_score: Minimum relevance score

    Returns:
        Filtered signals with relevance_score added
    """
    if not keywords and not competitors:
        return signals

    keywords = keywords or []
    filtered = []

    for signal in signals:
        score = score_relevance(
            signal,
            keywords=keywords,
            competitors=competitors,
            stop_phrases=stop_phrases,
        )

        if score >= min_score:
            signal_copy = signal.copy()
            signal_copy["relevance_score"] = score
            filtered.append(signal_copy)

    # Sort by relevance
    filtered.sort(key=lambda x: x["relevance_score"], reverse=True)

    return filtered


def filter_by_keywords(
    signals: list[dict[str, Any]],
    keywords: list[str],
    match_all: bool = False,
) -> list[dict[str, Any]]:
    """Filter signals that contain keywords.

    Args:
        signals: List of signals
        keywords: Keywords to match
        match_all: If True, require all keywords

    Returns:
        Filtered signals
    """
    filtered = []

    for signal in signals:
        text = _get_signal_text(signal).lower()

        if match_all:
            if all(kw.lower() in text for kw in keywords):
                filtered.append(signal)
        else:
            if any(kw.lower() in text for kw in keywords):
                filtered.append(signal)

    return filtered


def filter_by_date(
    signals: list[dict[str, Any]],
    since: str | None = None,
    until: str | None = None,
) -> list[dict[str, Any]]:
    """Filter signals by date range.

    Args:
        signals: List of signals
        since: Start date (ISO format)
        until: End date (ISO format)

    Returns:
        Filtered signals
    """
    from datetime import datetime

    filtered = []

    for signal in signals:
        date_str = signal.get("published_at") or signal.get("fetched_at")
        if not date_str:
            continue

        try:
            # Parse ISO date
            signal_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))

            if since:
                since_date = datetime.fromisoformat(since)
                if signal_date < since_date:
                    continue

            if until:
                until_date = datetime.fromisoformat(until)
                if signal_date > until_date:
                    continue

            filtered.append(signal)

        except (ValueError, TypeError):
            continue

    return filtered


def _get_signal_text(signal: dict[str, Any]) -> str:
    """Get searchable text from a signal."""
    parts = []

    for field in ["headline", "title", "text", "summary", "description"]:
        if value := signal.get(field):
            parts.append(str(value))

    return " ".join(parts)
