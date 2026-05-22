"""Cartesia TTS — not yet integrated."""
from __future__ import annotations

from typing import Any


def generate_tts(
    text: str,
    voice_id: str | None = None,
) -> dict[str, Any]:
    return {
        "success": False,
        "error": "Cartesia provider not implemented",
    }
