"""Content queue management."""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from agentcy.brand.core.brands import get_brand_dir
from agentcy.brand.core.config import utc_now


class QueueItem(BaseModel):
    """A queued content item."""

    id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    content: str
    platform: str | None = None
    scheduled_at: str | None = None
    status: str = "pending"  # pending, posted, failed
    created_at: str = Field(default_factory=lambda: utc_now().isoformat())
    metadata: dict[str, Any] = Field(default_factory=dict)


def get_queue_path(brand: str) -> Path:
    """Get the queue file path for a brand."""
    return get_brand_dir(brand) / "queue.json"


def load_queue(brand: str) -> list[QueueItem]:
    """Load the queue for a brand.

    Args:
        brand: Brand name

    Returns:
        List of queue items
    """
    queue_path = get_queue_path(brand)

    if not queue_path.exists():
        return []

    data = json.loads(queue_path.read_text())

    # Handle both list and dict formats
    if isinstance(data, dict):
        items = data.get("items", [])
    else:
        items = data

    return [QueueItem(**item) for item in items]


def save_queue(brand: str, items: list[QueueItem]) -> None:
    """Save the queue for a brand.

    Args:
        brand: Brand name
        items: Queue items to save
    """
    queue_path = get_queue_path(brand)
    queue_path.parent.mkdir(parents=True, exist_ok=True)

    data = {
        "updated_at": utc_now().isoformat(),
        "items": [item.model_dump() for item in items],
    }

    queue_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def add_to_queue(
    brand: str,
    content: str,
    platform: str | None = None,
    scheduled_at: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> QueueItem:
    """Add an item to the queue.

    Args:
        brand: Brand name
        content: Content text
        platform: Target platform
        scheduled_at: Optional scheduled time (ISO format)
        metadata: Optional metadata

    Returns:
        Created queue item
    """
    items = load_queue(brand)

    item = QueueItem(
        content=content,
        platform=platform,
        scheduled_at=scheduled_at,
        metadata=metadata or {},
    )

    items.append(item)
    save_queue(brand, items)

    return item


def get_queue(
    brand: str,
    status: str | None = None,
    platform: str | None = None,
) -> list[QueueItem]:
    """Get queue items with optional filtering.

    Args:
        brand: Brand name
        status: Filter by status
        platform: Filter by platform

    Returns:
        Filtered queue items
    """
    items = load_queue(brand)

    if status:
        items = [i for i in items if i.status == status]

    if platform:
        items = [i for i in items if i.platform == platform]

    return items


def get_queue_item(brand: str, item_id: str) -> QueueItem | None:
    """Get a specific queue item.

    Args:
        brand: Brand name
        item_id: Item ID

    Returns:
        Queue item or None
    """
    items = load_queue(brand)

    for item in items:
        if item.id == item_id:
            return item

    return None


def update_queue_item(
    brand: str,
    item_id: str,
    content: str | None = None,
    platform: str | None = None,
    status: str | None = None,
    scheduled_at: str | None = None,
) -> QueueItem | None:
    """Update a queue item.

    Args:
        brand: Brand name
        item_id: Item ID
        content: New content
        platform: New platform
        status: New status
        scheduled_at: New scheduled time

    Returns:
        Updated item or None if not found
    """
    items = load_queue(brand)

    for i, item in enumerate(items):
        if item.id == item_id:
            if content is not None:
                item.content = content
            if platform is not None:
                item.platform = platform
            if status is not None:
                item.status = status
            if scheduled_at is not None:
                item.scheduled_at = scheduled_at

            items[i] = item
            save_queue(brand, items)
            return item

    return None


def remove_from_queue(brand: str, item_id: str) -> bool:
    """Remove an item from the queue.

    Args:
        brand: Brand name
        item_id: Item ID

    Returns:
        True if removed, False if not found
    """
    items = load_queue(brand)
    original_len = len(items)

    items = [i for i in items if i.id != item_id]

    if len(items) < original_len:
        save_queue(brand, items)
        return True

    return False


def clear_queue(brand: str, status: str | None = None) -> int:
    """Clear the queue.

    Args:
        brand: Brand name
        status: Only clear items with this status

    Returns:
        Number of items removed
    """
    items = load_queue(brand)
    original_len = len(items)

    if status:
        items = [i for i in items if i.status != status]
    else:
        items = []

    save_queue(brand, items)
    return original_len - len(items)


def get_next_pending(brand: str, platform: str | None = None) -> QueueItem | None:
    """Get the next pending item to post.

    Args:
        brand: Brand name
        platform: Optional platform filter

    Returns:
        Next pending item or None
    """
    items = get_queue(brand, status="pending", platform=platform)

    # Sort by scheduled time, then created time
    items.sort(key=lambda x: x.scheduled_at or x.created_at)

    return items[0] if items else None
