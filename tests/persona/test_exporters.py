"""Tests for export formats."""

from __future__ import annotations

import json
from pathlib import Path

from agentcy.persona.exporters import export_voice_pack, get_exporter, list_formats
from agentcy.persona.persona import Persona

REPO_ROOT = Path(__file__).resolve().parents[1]
PROTOCOLS_DIR = REPO_ROOT.parent / "src" / "agentcy" / "protocols"
FIXTURES_DIR = Path(__file__).parent / "fixtures" / "voice_pack"


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text())


def test_voice_pack_export_matches_canonical_minimal_example():
    persona = Persona.load(FIXTURES_DIR / "minimal.persona.yaml")
    exported = json.loads(export_voice_pack(persona))
    expected = _load_json(PROTOCOLS_DIR / "examples" / "voice_pack.v1.minimal.json")

    assert exported == expected


def test_voice_pack_export_matches_canonical_rich_example():
    persona = Persona.load(FIXTURES_DIR / "rich.persona.yaml")
    exported = json.loads(export_voice_pack(persona))
    expected = _load_json(PROTOCOLS_DIR / "examples" / "voice_pack.v1.rich.json")

    assert exported == expected


def test_voice_pack_export_is_registered_and_stable():
    persona = Persona.load(FIXTURES_DIR / "rich.persona.yaml")
    exporter = get_exporter("voice-pack")

    first = exporter(persona)
    second = exporter(persona)

    assert first == second
    assert "voice-pack" in list_formats()
    assert json.loads(first)["artifact_type"] == "voice_pack.v1"
