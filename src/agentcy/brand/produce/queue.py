from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.storage import data_dir, ensure_dir


class QueueItem(BaseModel):
    id: str
    brand: str
    text: str
    platform: str | None = None
    created_at: str
    metadata: dict[str, Any] = Field(default_factory=dict)


def queue_path(brand: str) -> Path:
    directory = ensure_dir(data_dir() / "queues")
    return directory / f"{brand}.json"


def load_queue(brand: str) -> list[QueueItem]:
    path = queue_path(brand)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle) or []
    return [QueueItem(**item) for item in payload]


def save_queue(brand: str, items: list[QueueItem]) -> None:
    path = queue_path(brand)
    with path.open("w", encoding="utf-8") as handle:
        json.dump([item.model_dump() for item in items], handle, indent=2)


def enqueue(
    brand: str,
    text: str,
    platform: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> QueueItem:
    items = load_queue(brand)
    item = QueueItem(
        id=str(uuid.uuid4()),
        brand=brand,
        text=text,
        platform=platform,
        created_at=utc_now().isoformat(),
        metadata=metadata or {},
    )
    items.append(item)
    save_queue(brand, items)
    return item


def clear_queue(brand: str) -> None:
    save_queue(brand, [])
