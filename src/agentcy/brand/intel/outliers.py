"""Outlier detection for viral content."""
from __future__ import annotations

from typing import Any
import statistics


def detect_outliers(
    posts: list[dict[str, Any]],
    threshold: float = 50.0,
    metric: str = "engagement",
) -> list[dict[str, Any]]:
    """Detect viral/outlier posts.

    A post is considered an outlier if its engagement is threshold times
    higher than the median engagement.

    Args:
        posts: List of post data
        threshold: Multiplier above median to consider outlier (default 50x)
        metric: Metric to use for comparison ("engagement", "likes", "views")

    Returns:
        List of outlier posts with outlier_score added
    """
    if not posts:
        return []

    # Calculate engagement scores
    scores = []
    for post in posts:
        score = calculate_engagement(post, metric)
        scores.append(score)

    if not scores or all(s == 0 for s in scores):
        return []

    # Calculate median (exclude zeros)
    non_zero_scores = [s for s in scores if s > 0]
    if not non_zero_scores:
        return []

    median = statistics.median(non_zero_scores)
    threshold_value = median * threshold

    # Find outliers
    outliers = []
    for post, score in zip(posts, scores):
        if score >= threshold_value:
            post_copy = post.copy()
            post_copy["engagement_score"] = score
            post_copy["outlier_score"] = score / median if median > 0 else 0
            outliers.append(post_copy)

    # Sort by outlier score descending
    outliers.sort(key=lambda x: x["outlier_score"], reverse=True)

    return outliers


def calculate_engagement(post: dict[str, Any], metric: str = "engagement") -> float:
    """Calculate engagement score for a post.

    Args:
        post: Post data
        metric: Metric type

    Returns:
        Engagement score
    """
    if metric == "likes":
        return float(post.get("likes", 0))
    elif metric == "views":
        return float(post.get("views", 0))
    elif metric == "engagement":
        # Weighted engagement score
        likes = float(post.get("likes", 0))
        comments = float(post.get("comments", post.get("replies", 0)))
        shares = float(post.get("retweets", post.get("reposts", 0)))
        views = float(post.get("views", 0))

        # Weight: likes=1, comments=2, shares=3
        score = likes + (comments * 2) + (shares * 3)

        # If we have views, calculate engagement rate
        if views > 0:
            engagement_rate = score / views
            # Boost by view count (log scale)
            import math
            score = score * (1 + math.log10(max(views, 1)))

        return score
    else:
        raise ValueError(f"Unknown metric: {metric}")


def get_outlier_stats(posts: list[dict[str, Any]]) -> dict[str, Any]:
    """Get statistics about outliers in a post set.

    Args:
        posts: List of posts

    Returns:
        Statistics dict
    """
    if not posts:
        return {"count": 0}

    scores = [calculate_engagement(p) for p in posts]
    non_zero = [s for s in scores if s > 0]

    if not non_zero:
        return {"count": 0}

    return {
        "count": len(posts),
        "median_engagement": statistics.median(non_zero),
        "mean_engagement": statistics.mean(non_zero),
        "max_engagement": max(non_zero),
        "min_engagement": min(non_zero),
        "std_dev": statistics.stdev(non_zero) if len(non_zero) > 1 else 0,
    }
