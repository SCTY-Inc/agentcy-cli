"""Reve image generation provider.

This provider name is reserved, but the runtime is not yet shipped here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def generate_with_reve(
    direction: str,
    brand: str | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Return an explicit unsupported result for the unshipped Reve runtime."""
    return {
        "success": False,
        "error": "Reve image generation is not implemented in this build.",
        "prompt": direction,
        "brand": brand,
        "output_path": str(output_path) if output_path else None,
    }
