"""Gemini image generation provider."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any


def generate_with_gemini(
    direction: str,
    brand: str | None = None,
    style_ref: Path | None = None,
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Generate image using Gemini.

    Args:
        direction: Image prompt
        brand: Brand name
        style_ref: Style reference image
        output_path: Output path

    Returns:
        Result dict with image_path or error
    """
    try:
        from google import genai
    except ImportError:
        raise ImportError("google-genai required. Install with: pip install agentcy-compass[image]")

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError("GOOGLE_API_KEY environment variable required")

    client = genai.Client(api_key=api_key)

    # Build prompt with brand context
    prompt_parts = [direction]

    if brand:
        prompt_parts.insert(0, f"For the brand '{brand}':")

    prompt = " ".join(prompt_parts)

    try:
        response = client.models.generate_images(
            model="imagen-3.0-generate-002",
            prompt=prompt,
            config={
                "number_of_images": 1,
            },
        )

        # Save image if we have output
        if response.generated_images and output_path:
            image = response.generated_images[0]
            image.image.save(str(output_path))

            return {
                "success": True,
                "image_path": str(output_path),
                "prompt": prompt,
            }

        return {
            "success": True,
            "prompt": prompt,
            "note": "Image generated but not saved (no output path)",
        }

    except (ValueError, OSError, RuntimeError) as e:
        return {
            "success": False,
            "error": str(e),
            "prompt": prompt,
        }
