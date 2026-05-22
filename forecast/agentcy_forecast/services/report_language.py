"""
Report language detection utility.
"""
from __future__ import annotations


def _detect_language(text: str) -> str:
    """
    Detect language based on CJK character percentage.

    Args:
        text: Text to analyze

    Returns:
        "zh" if >5% of non-whitespace characters are CJK, else "en"
    """
    if not text:
        return "en"

    # Count CJK characters
    cjk_count = 0
    total_count = 0

    for char in text:
        if not char.isspace():
            total_count += 1
            # Check if character is in CJK ranges
            if "一" <= char <= "鿿" or "㐀" <= char <= "䶿":
                cjk_count += 1

    if total_count == 0:
        return "en"

    cjk_ratio = cjk_count / total_count
    return "zh" if cjk_ratio > 0.05 else "en"
