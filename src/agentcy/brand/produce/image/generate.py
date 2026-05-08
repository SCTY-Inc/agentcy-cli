"""Image generation orchestration."""
from __future__ import annotations

from pathlib import Path
from typing import Any


def generate_image(
    direction: str,
    brand: str | None = None,
    style_ref: Path | None = None,
    output_path: Path | None = None,
    provider: str = "gemini",
) -> dict[str, Any]:
    """Generate an image.

    Args:
        direction: Image prompt/direction
        brand: Brand name for style context
        style_ref: Optional style reference image
        output_path: Optional output path
        provider: Image provider ("gemini", "reve")

    Returns:
        Generation result with image path or URL
    """
    if provider == "gemini":
        from agentcy.brand.produce.image.providers.gemini import generate_with_gemini
        return generate_with_gemini(direction, brand, style_ref, output_path)
    elif provider == "reve":
        from agentcy.brand.produce.image.providers.reve import generate_with_reve
        return generate_with_reve(direction, brand, output_path)
    else:
        raise ValueError(f"Unknown image provider: {provider}")
