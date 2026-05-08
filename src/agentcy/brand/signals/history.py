"""Signal history storage (JSONL-based)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.storage import data_dir


def signals_history_dir() -> Path:
    """Get the signals history directory."""
    path = data_dir() / "signals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_history_file(brand: str) -> Path:
    """Get the history file path for a brand."""
    return signals_history_dir() / f"{brand}.jsonl"


def append_signals(
    brand: str,
    signals: list[dict[str, Any]],
    deduplicate: bool = True,
) -> int:
    """Append signals to history.

    Args:
        brand: Brand name
        signals: Signals to append
        deduplicate: Skip duplicates based on URL

    Returns:
        Number of signals appended
    """
    history_file = get_history_file(brand)

    # Load existing URLs for deduplication
    existing_urls = set()
    if deduplicate and history_file.exists():
        with open(history_file) as f:
            for line in f:
                if line.strip():
                    entry = json.loads(line)
                    if url := entry.get("url"):
                        existing_urls.add(url)


    count = 0
    with open(history_file, "a") as f:
        for signal in signals:
            # Skip duplicates
            if deduplicate and signal.get("url") in existing_urls:
                continue

            # Add timestamp
            signal["stored_at"] = utc_now().isoformat()

            f.write(json.dumps(signal, ensure_ascii=False) + "\n")
            count += 1

            if url := signal.get("url"):
                existing_urls.add(url)

    return count


def query_signals(
    brand: str,
    query: str | None = None,
    since: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Query historical signals.

    Args:
        brand: Brand name
        query: Text search query
        since: ISO date string for minimum date
        limit: Maximum results

    Returns:
        List of matching signals
    """
    history_file = get_history_file(brand)

    if not history_file.exists():
        return []

    signals = []
    query_lower = query.lower() if query else None

    # Parse since date
    since_date = None
    if since:
        try:
            since_date = datetime.fromisoformat(since)
        except ValueError:
            # Try parsing relative dates like "7d"
            if since.endswith("d"):
                days = int(since[:-1])
                since_date = utc_now() - timedelta(days=days)

    with open(history_file) as f:
        for line in f:
            if not line.strip():
                continue

            signal = json.loads(line)

            # Date filter
            if since_date:
                stored = signal.get("stored_at") or signal.get("published_at")
                if stored:
                    try:
                        signal_date = datetime.fromisoformat(stored.replace("Z", "+00:00"))
                        if signal_date < since_date:
                            continue
                    except ValueError:
                        pass

            # Text query filter
            if query_lower:
                text = " ".join(
                    str(signal.get(f, ""))
                    for f in ["headline", "title", "text", "summary"]
                ).lower()
                if query_lower not in text:
                    continue

            signals.append(signal)

    # Return most recent first, limited
    signals.reverse()
    return signals[:limit]


def get_signal_count(brand: str) -> int:
    """Get total signal count for a brand."""
    history_file = get_history_file(brand)

    if not history_file.exists():
        return 0

    count = 0
    with open(history_file) as f:
        for line in f:
            if line.strip():
                count += 1

    return count


def deduplicate_history(brand: str) -> int:
    """Remove duplicate signals from history.

    Args:
        brand: Brand name

    Returns:
        Number of duplicates removed
    """
    history_file = get_history_file(brand)

    if not history_file.exists():
        return 0

    seen_urls = set()
    unique_signals = []
    duplicates = 0

    with open(history_file) as f:
        for line in f:
            if not line.strip():
                continue

            signal = json.loads(line)
            url = signal.get("url")

            if url and url in seen_urls:
                duplicates += 1
                continue

            unique_signals.append(signal)
            if url:
                seen_urls.add(url)

    # Rewrite file
    with open(history_file, "w") as f:
        for signal in unique_signals:
            f.write(json.dumps(signal, ensure_ascii=False) + "\n")

    return duplicates
