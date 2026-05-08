from __future__ import annotations

from pathlib import Path

import pytest

from agentcy.forecast.utils.file_parser import FileParser


def test_extract_from_multiple_keeps_expected_input_failures_inline(tmp_path: Path):
    good = tmp_path / "notes.txt"
    good.write_text("hello world", encoding="utf-8")
    missing = tmp_path / "missing.txt"
    bad = tmp_path / "bad.csv"
    bad.write_text("a,b,c\n", encoding="utf-8")

    merged = FileParser.extract_from_multiple([str(good), str(missing), str(bad)])

    assert "=== Document 1: notes.txt ===\nhello world" in merged
    assert f"{missing} (extraction failed: File not found: {missing})" in merged
    assert "bad.csv (extraction failed: Unsupported file format: .csv)" in merged


def test_extract_from_multiple_does_not_hide_unexpected_errors(monkeypatch: pytest.MonkeyPatch):
    def explode(_file_path: str) -> str:
        raise AssertionError("unexpected bug")

    monkeypatch.setattr(FileParser, "extract_text", explode)

    with pytest.raises(AssertionError, match="unexpected bug"):
        FileParser.extract_from_multiple(["example.txt"])
