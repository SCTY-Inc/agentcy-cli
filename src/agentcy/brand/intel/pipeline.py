"""Intel pipeline orchestration."""
from __future__ import annotations

from typing import Any

from agentcy.brand.core.brands import get_brand_intel_dir, load_brand_config


def run_intel_pipeline(
    brand: str,
    skip_scrape: bool = False,
    platforms: list[str] | None = None,
) -> dict[str, Any]:
    """Run the full intel pipeline for a brand.

    Pipeline stages:
    1. Scrape social media posts (Apify)
    2. Detect outliers (viral content)
    3. Extract hooks (patterns)

    Args:
        brand: Brand name
        skip_scrape: Skip the scraping stage
        platforms: Platforms to scrape (default: all configured)

    Returns:
        Pipeline results
    """
    from agentcy.brand.intel.hooks import extract_hooks
    from agentcy.brand.intel.outliers import detect_outliers
    from agentcy.brand.intel.scrapers.apify import scrape_posts

    intel_dir = get_brand_intel_dir(brand)
    config = load_brand_config(brand)

    results = {
        "brand": brand,
        "stages": {},
    }

    # Stage 1: Scrape
    if not skip_scrape:
        handles = config.get("handles", {})
        platforms = platforms or list(handles.keys())

        posts = []
        for platform in platforms:
            if handle := handles.get(platform):
                platform_posts = scrape_posts(platform, handle)
                posts.extend(platform_posts)

        results["stages"]["scrape"] = {
            "posts_collected": len(posts),
            "platforms": platforms,
        }
    else:
        # Load existing posts
        posts_file = intel_dir / "posts.json"
        if posts_file.exists():
            import json
            posts = json.loads(posts_file.read_text())
        else:
            posts = []

    # Stage 2: Detect outliers
    outliers = detect_outliers(posts)
    results["stages"]["outliers"] = {
        "found": len(outliers),
    }

    # Save outliers
    import json
    outliers_file = intel_dir / "outliers.json"
    outliers_file.write_text(json.dumps(outliers, indent=2, ensure_ascii=False))

    # Stage 3: Extract hooks
    hooks = extract_hooks(outliers, brand=brand)
    results["stages"]["hooks"] = {
        "extracted": len(hooks),
    }

    # Save hooks
    hooks_file = intel_dir / "hooks.json"
    hooks_file.write_text(json.dumps(hooks, indent=2, ensure_ascii=False))

    return results
