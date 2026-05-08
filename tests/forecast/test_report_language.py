"""Unit tests for report language detection."""

from __future__ import annotations

from agentcy.forecast.services.report_language import _detect_language


def test_empty_string_returns_en():
    assert _detect_language("") == "en"


def test_pure_english_returns_en():
    assert _detect_language("Hello world, this is a test.") == "en"


def test_pure_cjk_returns_zh():
    # A string of Chinese characters
    assert _detect_language("你好世界这是一个测试句子") == "zh"


def test_mixed_mostly_english_returns_en():
    # 1 CJK char out of 25 non-space = 4% < 5% threshold → "en"
    assert _detect_language("Hello world this is english 好") == "en"


def test_mixed_mostly_cjk_returns_zh():
    # >5% CJK
    assert _detect_language("你好 hello") == "zh"


def test_whitespace_only_returns_en():
    assert _detect_language("   \t\n  ") == "en"


def test_punctuation_only_returns_en():
    assert _detect_language("!@#$%^&*()") == "en"


def test_exactly_at_threshold():
    # Build a string where CJK is exactly 5%: 1 CJK char out of 20 non-space chars → 5% → still "en"
    text = "a" * 19 + "好"
    assert _detect_language(text) == "en"


def test_just_above_threshold():
    # 2 CJK chars out of 20 non-space = 10% → "zh"
    text = "a" * 18 + "你好"
    assert _detect_language(text) == "zh"


def test_numbers_not_cjk():
    assert _detect_language("12345 6789 0") == "en"
