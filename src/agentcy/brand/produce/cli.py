"""Produce CLI commands."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from agentcy.brand.cli_utils import emit, status

produce_app = typer.Typer(help="Content production commands.")
console = Console()


@produce_app.command("copy")
def copy_cmd(
    topic: str = typer.Argument(..., help="Content topic"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name"),
    platform: str = typer.Option("twitter", "--platform", "-p", help="Target platform"),
    format: str = typer.Option("json", "--format", "-f", help="Output format"),
) -> None:
    """Generate copy for a platform."""
    from agentcy.brand.core.brands import load_brand_config
    from agentcy.brand.produce.copy import generate_copy

    voice = None
    hooks = None

    if brand:
        try:
            config = load_brand_config(brand)
        except ValueError:
            pass  # Brand not found — proceed without brand config
        else:
            voice = config.get("voice")

            # Load hooks if available
            from agentcy.brand.core.brands import get_brand_intel_dir
            import json

            hooks_file = get_brand_intel_dir(brand) / "hooks.json"
            if hooks_file.exists():
                hooks = json.loads(hooks_file.read_text())[:5]

    result = generate_copy(
        topic=topic,
        brand=brand,
        platform=platform,
        voice=voice,
        hooks=hooks,
    )

    emit(result, format)


@produce_app.command("thread")
def thread_cmd(
    topic: str = typer.Argument(..., help="Thread topic"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name"),
    tweets: int = typer.Option(5, "--tweets", "-n", help="Number of tweets"),
    format: str = typer.Option("json", "--format", "-f", help="Output format"),
) -> None:
    """Generate a Twitter/X thread."""
    from agentcy.brand.produce.copy import generate_thread

    result = generate_thread(topic=topic, brand=brand, num_tweets=tweets)

    if format == "text":
        for i, tweet in enumerate(result, 1):
            console.print(f"[bold]{i}/[/bold] {tweet}")
            console.print()
    else:
        emit({"tweets": result}, format)


@produce_app.command("image")
def image_cmd(
    direction: str = typer.Argument(..., help="Image direction/prompt"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name"),
    style: Path | None = typer.Option(None, "--style", "-s", help="Style reference image"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output path"),
    format: str = typer.Option("json", "--format", "-f", help="Output format"),
) -> None:
    """Generate an image."""
    from agentcy.brand.produce.image import generate_image

    result = generate_image(
        direction=direction,
        brand=brand,
        style_ref=style,
        output_path=output,
    )

    emit(result, format)


@produce_app.command("video")
def video_cmd(
    brief: str = typer.Argument(..., help="Video brief"),
    brand: str | None = typer.Option(None, "--brand", "-b", help="Brand name"),
    duration: int = typer.Option(30, "--duration", "-d", help="Duration in seconds"),
    format: str = typer.Option("json", "--format", "-f", help="Output format"),
) -> None:
    """Return the explicit unsupported result for the current video surface."""
    from agentcy.brand.produce.video import generate_video

    result = generate_video(brief=brief, brand=brand, duration=duration)

    emit(result, format)


@produce_app.command("explore")
def explore_cmd(
    topic: str = typer.Argument(..., help="Topic to explore"),
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    platforms: str = typer.Option("twitter,linkedin", "--platforms", "-p", help="Platforms (comma-separated)"),
    add_to_queue: bool = typer.Option(True, "--queue/--no-queue", help="Add to queue"),
    format: str = typer.Option("json", "--format", "-f", help="Output format"),
) -> None:
    """Full exploration flow: generate copy for multiple platforms and optionally queue."""
    from agentcy.brand.core.brands import get_brand_intel_dir, load_brand_config
    from agentcy.brand.produce.copy import generate_copy
    from agentcy.brand.produce.queue import enqueue
    import json

    config = load_brand_config(brand)
    voice = config.get("voice")

    # Load hooks
    hooks = None
    hooks_file = get_brand_intel_dir(brand) / "hooks.json"
    if hooks_file.exists():
        hooks = json.loads(hooks_file.read_text())[:5]

    # Load learnings
    learnings = None
    learnings_file = get_brand_intel_dir(brand).parent / "learnings.json"
    if learnings_file.exists():
        learnings_data = json.loads(learnings_file.read_text())
        learnings = learnings_data.get("suggestions", [])[:5]

    platform_list = [p.strip() for p in platforms.split(",")]
    results = []

    for platform in platform_list:
        status(f"Generating {platform} content...")

        result = generate_copy(
            topic=topic,
            brand=brand,
            platform=platform,
            voice=voice,
            hooks=hooks,
            learnings=learnings,
        )

        results.append({"platform": platform, **result})

        if add_to_queue and result.get("main"):
            enqueue(brand, result["main"], platform=platform)
            status("  Added to queue")

    emit(results, format)
