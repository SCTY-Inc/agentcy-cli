"""Shared simulation workflow helpers."""

import json
import os
from datetime import datetime
from typing import Any, Dict, Tuple

from ..config import Config
from ..utils.logger import get_logger

logger = get_logger("mirofish.tools.simulation_support")


PreparedState = Tuple[bool, Dict[str, Any]]


def _simulation_dir(simulation_id: str) -> str:
    return os.path.join(Config.OASIS_SIMULATION_DATA_DIR, simulation_id)


def _load_json_file(path: str) -> Any:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def _save_state_file(path: str, state_data: Dict[str, Any]) -> None:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(state_data, handle, ensure_ascii=False, indent=2)


def check_simulation_prepared(simulation_id: str) -> PreparedState:
    """Check whether a simulation has all artifacts needed to run."""
    simulation_dir = _simulation_dir(simulation_id)
    if not os.path.exists(simulation_dir):
        return False, {"reason": "Simulation directory does not exist"}

    required_files = [
        "state.json",
        "simulation_config.json",
        "reddit_profiles.json",
        "twitter_profiles.csv",
    ]

    existing_files = []
    missing_files = []
    for filename in required_files:
        path = os.path.join(simulation_dir, filename)
        if os.path.exists(path):
            existing_files.append(filename)
        else:
            missing_files.append(filename)

    if missing_files:
        return False, {
            "reason": "Missing required files",
            "missing_files": missing_files,
            "existing_files": existing_files,
        }

    state_file = os.path.join(simulation_dir, "state.json")
    try:
        state_data = _load_json_file(state_file)
        if not isinstance(state_data, dict):
            raise ValueError("state.json must contain an object")

        status = state_data.get("status", "")
        config_generated = state_data.get("config_generated", False)
        prepared_statuses = ["ready", "preparing", "running", "completed", "stopped", "failed"]

        if status in prepared_statuses and config_generated:
            profiles_file = os.path.join(simulation_dir, "reddit_profiles.json")
            profiles_count = 0
            if os.path.exists(profiles_file):
                profiles_data = _load_json_file(profiles_file)
                profiles_count = len(profiles_data) if isinstance(profiles_data, list) else 0

            if status == "preparing":
                try:
                    state_data["status"] = "ready"
                    state_data["updated_at"] = datetime.now().isoformat()
                    _save_state_file(state_file, state_data)
                    status = "ready"
                    logger.info(f"Auto-updated simulation status: {simulation_id} preparing -> ready")
                except OSError as exc:
                    logger.warning(f"Failed to auto-update simulation status: {exc}")

            return True, {
                "status": status,
                "entities_count": state_data.get("entities_count", 0),
                "profiles_count": profiles_count,
                "entity_types": state_data.get("entity_types", []),
                "config_generated": config_generated,
                "created_at": state_data.get("created_at"),
                "updated_at": state_data.get("updated_at"),
                "existing_files": existing_files,
            }

        return False, {
            "reason": f"Status not ready for run: status={status}, config_generated={config_generated}",
            "status": status,
            "config_generated": config_generated,
            "existing_files": existing_files,
        }
    except (OSError, ValueError, json.JSONDecodeError, TypeError) as exc:
        return False, {"reason": f"Failed to read state file: {exc}"}
