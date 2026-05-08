"""Intel CLI commands."""
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console

from agentcy.brand.cli_utils import emit, status

intel_app = typer.Typer(help="Intelligence gathering commands.")
console = Console()


@intel_app.command("scrape")
def scrape(
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    platform: str | None = typer.Option(None, "--platform", "-p", help="Specific platform"),
    limit: int = typer.Option(100, "--limit", "-l", help="Max posts to scrape"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Scrape social media posts for a brand."""
    from agentcy.brand.core.brands import load_brand_config
    from agentcy.brand.intel.scrapers.apify import scrape_posts

    config = load_brand_config(brand)
    handles = config.get("handles", {})

    if platform:
        platforms = [platform]
    else:
        platforms = list(handles.keys())

    all_posts = []
    for p in platforms:
        if handle := handles.get(p):
            status(f"Scraping {p}: @{handle}...")
            posts = scrape_posts(p, handle, limit=limit)
            all_posts.extend(posts)
            status(f"  Found {len(posts)} posts")

    emit(all_posts, format)


@intel_app.command("outliers")
def outliers(
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    threshold: float = typer.Option(50.0, "--threshold", "-t", help="Outlier threshold (x median)"),
    input_file: Path | None = typer.Option(None, "--input", "-i", help="Input posts JSON file"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Detect viral/outlier posts."""
    import json

    from agentcy.brand.core.brands import get_brand_intel_dir
    from agentcy.brand.intel.outliers import detect_outliers, get_outlier_stats

    if input_file:
        posts = json.loads(input_file.read_text())
    else:
        intel_dir = get_brand_intel_dir(brand)
        posts_file = intel_dir / "posts.json"
        if not posts_file.exists():
            status("[red]No posts found. Run scrape first.[/red]")
            raise typer.Exit(1)
        posts = json.loads(posts_file.read_text())

    outlier_posts = detect_outliers(posts, threshold=threshold)
    stats = get_outlier_stats(posts)

    status(f"Found {len(outlier_posts)} outliers from {len(posts)} posts")
    status(f"Threshold: {threshold}x median ({stats.get('median_engagement', 0):.0f})")

    emit(outlier_posts, format)


@intel_app.command("hooks")
def hooks(
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    limit: int = typer.Option(10, "--limit", "-l", help="Max hooks to extract"),
    input_file: Path | None = typer.Option(None, "--input", "-i", help="Input outliers JSON file"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Extract hooks from viral posts."""
    import json

    from agentcy.brand.core.brands import get_brand_intel_dir
    from agentcy.brand.intel.hooks import extract_hooks

    if input_file:
        outlier_posts = json.loads(input_file.read_text())
    else:
        intel_dir = get_brand_intel_dir(brand)
        outliers_file = intel_dir / "outliers.json"
        if not outliers_file.exists():
            status("[red]No outliers found. Run outliers first.[/red]")
            raise typer.Exit(1)
        outlier_posts = json.loads(outliers_file.read_text())

    extracted = extract_hooks(outlier_posts, brand=brand, limit=limit)
    status(f"Extracted {len(extracted)} hooks")

    emit(extracted, format)


@intel_app.command("pipeline")
def pipeline(
    brand: str = typer.Option(..., "--brand", "-b", help="Brand name"),
    skip_scrape: bool = typer.Option(False, "--skip-scrape", help="Skip scraping stage"),
    format: str | None = typer.Option(None, "--format", "-f", help="Output format"),
) -> None:
    """Run the full intel pipeline."""
    from agentcy.brand.intel.pipeline import run_intel_pipeline

    status(f"[bold]Running intel pipeline for {brand}[/bold]")

    results = run_intel_pipeline(brand, skip_scrape=skip_scrape)

    for stage, data in results.get("stages", {}).items():
        status(f"  {stage}: {data}")

    emit(results, format)
