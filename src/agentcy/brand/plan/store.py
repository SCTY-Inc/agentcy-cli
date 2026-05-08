"""Campaign persistence."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any
import uuid

from agentcy.brand.core.config import utc_now
from agentcy.brand.core.storage import data_dir


def campaigns_dir() -> Path:
    """Get the campaigns directory."""
    path = data_dir() / "campaigns"
    path.mkdir(parents=True, exist_ok=True)
    return path


def generate_campaign_id() -> str:
    """Generate a unique campaign ID."""
    return str(uuid.uuid4())[:8]


def save_campaign(
    campaign_id: str | None = None,
    brief: str | None = None,
    brand: str | None = None,
    stages: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> str:
    """Save campaign state.

    Args:
        campaign_id: Optional ID (generates if not provided)
        brief: Campaign brief
        brand: Brand name
        stages: Stage results (research, strategy, creative, activation)
        metadata: Additional metadata

    Returns:
        Campaign ID
    """
    campaign_id = campaign_id or generate_campaign_id()

    campaign = {
        "id": campaign_id,
        "brief": brief,
        "brand": brand,
        "stages": stages or {},
        "metadata": metadata or {},
        "created_at": utc_now().isoformat(),
        "updated_at": utc_now().isoformat(),
    }

    path = campaigns_dir() / f"{campaign_id}.json"
    path.write_text(json.dumps(campaign, indent=2, ensure_ascii=False))

    return campaign_id


def load_campaign(campaign_id: str) -> dict[str, Any]:
    """Load campaign state.

    Args:
        campaign_id: Campaign ID

    Returns:
        Campaign data

    Raises:
        ValueError: If campaign not found
    """
    path = campaigns_dir() / f"{campaign_id}.json"

    if not path.exists():
        raise ValueError(f"Campaign not found: {campaign_id}")

    return json.loads(path.read_text())


def update_campaign(
    campaign_id: str,
    stage: str,
    result: dict[str, Any],
) -> dict[str, Any]:
    """Update a campaign stage.

    Args:
        campaign_id: Campaign ID
        stage: Stage name (research, strategy, creative, activation)
        result: Stage result

    Returns:
        Updated campaign
    """
    campaign = load_campaign(campaign_id)

    campaign["stages"][stage] = result
    campaign["updated_at"] = utc_now().isoformat()

    path = campaigns_dir() / f"{campaign_id}.json"
    path.write_text(json.dumps(campaign, indent=2, ensure_ascii=False))

    return campaign


def list_campaigns(limit: int = 20) -> list[dict[str, Any]]:
    """List saved campaigns.

    Args:
        limit: Maximum campaigns to return

    Returns:
        List of campaign summaries
    """
    campaigns = []

    for path in sorted(campaigns_dir().glob("*.json"), reverse=True):
        try:
            data = json.loads(path.read_text())
            campaigns.append({
                "id": data.get("id"),
                "brief": data.get("brief", "")[:100],
                "brand": data.get("brand"),
                "stages": list(data.get("stages", {}).keys()),
                "created_at": data.get("created_at"),
            })
        except (json.JSONDecodeError, KeyError):
            continue

        if len(campaigns) >= limit:
            break

    return campaigns


def delete_campaign(campaign_id: str) -> bool:
    """Delete a campaign.

    Args:
        campaign_id: Campaign ID

    Returns:
        True if deleted, False if not found
    """
    path = campaigns_dir() / f"{campaign_id}.json"

    if path.exists():
        path.unlink()
        return True

    return False
