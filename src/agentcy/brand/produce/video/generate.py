"""Video generation surface.

The CLI entrypoint remains in place, but this repo build does not yet ship a
video runtime.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def generate_video(
    brief: str,
    brand: str | None = None,
    duration: int = 30,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Return an explicit unsupported result for the unshipped video runtime."""
    return {
        "success": False,
        "error": "Video generation is not implemented in this build.",
        "brief": brief,
        "brand": brand,
        "duration": duration,
        "output_path": str(output_path) if output_path else None,
    }
