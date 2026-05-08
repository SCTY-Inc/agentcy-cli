from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]

from agentcy.brand.plan.brief_v1 import (  # noqa: E402
    build_brief_v1,
    load_voice_pack_v1,
    write_brief_v1,
)
from agentcy.persona.exporters import export_voice_pack  # noqa: E402
from agentcy.persona.persona import Persona  # noqa: E402

PROTOCOLS_DIR = ROOT / "src" / "agentcy" / "protocols"
EXAMPLES_DIR = PROTOCOLS_DIR / "examples"
VOICE_FIXTURES_DIR = ROOT / "tests" / "fixtures" / "voice_pack"
BRAND_OS_FIXTURES_DIR = ROOT / "tests" / "fixtures"


class _Voice:
    def __init__(self, tone: str | None = None):
        self.tone = tone


class _Identity:
    def __init__(self, tone: str | None = None):
        self.voice = _Voice(tone=tone)


class _Profile:
    def __init__(self, tone: str | None = None, platforms: dict | None = None):
        self.identity = _Identity(tone=tone)
        self.platforms = platforms or {}


@pytest.fixture(scope="module")
def voice_pack_schema() -> dict:
    return json.loads((PROTOCOLS_DIR / "schemas" / "voice_pack.v1.schema.json").read_text())


@pytest.fixture(scope="module")
def brief_schema() -> dict:
    return json.loads((PROTOCOLS_DIR / "schemas" / "brief.v1.schema.json").read_text())


@pytest.fixture(scope="module")
def lineage_rules() -> str:
    return (PROTOCOLS_DIR / "lineage-rules.md").read_text()


def test_cli_prsna_voice_pack_output_validates_against_canonical_schema(voice_pack_schema: dict):
    persona = Persona.load(VOICE_FIXTURES_DIR / "rich.persona.yaml")
    payload = json.loads(export_voice_pack(persona))

    Draft202012Validator(voice_pack_schema).validate(payload)
    assert payload["writer"] == {"repo": "cli-prsna", "module": "agentcy-vox"}
    assert payload["voice_pack_id"] == "givecare.voice.fall-checkin.v1"
    assert payload["brand_id"] == "givecare.brand.core"


def test_brand_os_brief_output_validates_against_canonical_schema_and_lineage(
    monkeypatch: pytest.MonkeyPatch,
    brief_schema: dict,
    lineage_rules: str,
    tmp_path: Path,
):
    monkeypatch.setattr(
        "agentcy.brand.plan.brief_v1.load_brand_profile",
        lambda brand: _Profile(tone="steady", platforms={"email": {}, "linkedin": {}}),
    )

    voice_pack_path = tmp_path / "voice_pack.v1.json"
    voice_pack_path.write_text(
        export_voice_pack(Persona.load(VOICE_FIXTURES_DIR / "rich.persona.yaml"))
    )
    voice_pack = load_voice_pack_v1(voice_pack_path)

    brief = build_brief_v1(
        brief="Increase caregiver response to seasonal planning content.",
        brand="GiveCare",
        voice_pack_id=None,
        voice_pack=voice_pack,
        campaign_id="givecare.campaign.fall-checkin.2026-04-12",
        signal_id="givecare.signal.support-calls.2026-04",
        research_result={
            "insights": ["Caregivers want concrete next steps before routines change."],
            "assumptions": ["Email and LinkedIn are the clearest first channels."],
            "sources": [{"title": "support-call-notes"}],
        },
        strategy_result={
            "positioning": "Make early planning feel supportive and manageable.",
            "value_proposition": "One shared checklist makes the next conversation easier.",
        },
        creative_result={
            "ctas": ["Download the checklist."],
            "headlines": [{"text": "Before fall gets busy, make caregiving feel lighter"}],
            "body_copy": ["Start with one shared checklist and one simple family conversation."],
            "tone_notes": ["actionable", "warm"],
        },
        activation_result={
            "channels": [
                {"channel": "email", "objective": "Engagement", "content_types": ["email"]},
                {
                    "channel": "linkedin",
                    "objective": "Reach caregivers",
                    "content_types": ["social-post"],
                },
            ],
            "risks": ["Avoid medical claims."],
        },
        policy_verdict="approved",
        policy_confidence=0.94,
    )

    brief_path = tmp_path / "brief.v1.json"
    write_brief_v1(brief_path, brief)
    payload = json.loads(brief_path.read_text())

    Draft202012Validator(brief_schema).validate(payload)
    assert payload["writer"] == {"repo": "brand-os", "module": "agentcy-compass"}
    assert payload["writer"]["repo"] != "cli-agency"
    assert payload["brand_id"] == voice_pack.brand_id
    assert payload["voice_pack_id"] == voice_pack.voice_pack_id
    assert payload["lineage"]["source_voice_pack_id"] == voice_pack.voice_pack_id
    assert payload["lineage"]["signal_id"] == "givecare.signal.support-calls.2026-04"
    assert "brief.v1" in lineage_rules and "run_result.v1" in lineage_rules
    assert "| `brief.v1` | `brand-os` | `agentcy-compass` |" in lineage_rules
    assert "must not appear as a `brief.v1` writer or protocol authority" in lineage_rules
    assert "| `brief.v1` | `cli-agency` |" not in lineage_rules


def test_brief_v1_canonical_example_and_brand_os_mirror_still_point_to_brand_os_only():
    canonical_payload = json.loads((EXAMPLES_DIR / "brief.v1.rich.json").read_text())
    mirror_payload = json.loads((BRAND_OS_FIXTURES_DIR / "brief.v1.rich.mirror.json").read_text())

    assert canonical_payload == mirror_payload
    assert canonical_payload["writer"] == {"repo": "brand-os", "module": "agentcy-compass"}
    assert canonical_payload["writer"]["repo"] != "cli-agency"
