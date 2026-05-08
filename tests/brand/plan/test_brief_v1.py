from __future__ import annotations

import importlib
import json
from pathlib import Path

from typer.testing import CliRunner

from agentcy.brand.cli import app
from agentcy.brand.plan import store as plan_store
from agentcy.brand.plan.brief_v1 import (
    BriefV1,
    build_brief_v1,
    load_voice_pack_v1,
    write_brief_v1,
)


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


REPO = Path(__file__).resolve().parents[3]
PROTOCOLS = REPO / "src" / "agentcy" / "protocols" / "examples"
FIXTURES = REPO / "tests" / "fixtures"
RESEARCH_STAGE = importlib.import_module("agentcy.brand.plan.stages.research")
STRATEGY_STAGE = importlib.import_module("agentcy.brand.plan.stages.strategy")
CREATIVE_STAGE = importlib.import_module("agentcy.brand.plan.stages.creative")
ACTIVATION_STAGE = importlib.import_module("agentcy.brand.plan.stages.activation")
runner = CliRunner()


def test_repo_local_brief_fixture_mirrors_parent_canonical_example_exactly():
    parent_payload = json.loads((PROTOCOLS / "brief.v1.rich.json").read_text())
    mirror_payload = json.loads((FIXTURES / "brief.v1.rich.mirror.json").read_text())

    assert mirror_payload == parent_payload
    assert BriefV1.model_validate(mirror_payload).writer.repo == "brand-os"


def test_build_brief_v1_maps_plan_outputs(monkeypatch):
    monkeypatch.setattr(
        "agentcy.brand.plan.brief_v1.load_brand_profile",
        lambda brand: _Profile(tone="steady", platforms={"linkedin": {}, "email": {}}),
    )

    brief = build_brief_v1(
        brief="Increase caregiver response to a fall planning checklist.",
        brand="GiveCare",
        voice_pack_id="givecare.voice.default.v1",
        campaign_id="givecare.campaign.fall-checkin.2026-04-12",
        signal_id="givecare.signal.support-calls.2026-04",
        research_result={
            "insights": ["Families need practical fall planning guidance."],
            "assumptions": ["Email remains the highest-intent channel."],
            "sources": [{"title": "support-call-notes"}],
        },
        strategy_result={
            "positioning": "Position planning as relief, not more work.",
            "value_proposition": "Simple planning reduces caregiver stress.",
            "target_audience": {
                "name": "Family caregivers",
                "description": "Adult children coordinating care from a distance.",
                "pain_points": ["Information is scattered across the family."],
                "motivations": ["Reduce last-minute stress for everyone involved."],
            },
            "messaging_pillars": ["Relief through preparation", "Simple shared coordination"],
            "proof_points": ["Checklist users complete key planning tasks faster."],
            "risks": ["Do not imply guaranteed clinical outcomes."],
        },
        creative_result={
            "ctas": ["Download the fall care checklist."],
            "headlines": [{"text": "A calmer way to prepare for fall caregiving"}],
            "body_copy": ["A short plan today can make the next family decision easier tomorrow."],
            "tone_notes": ["warm", "specific"],
        },
        activation_result={
            "channels": [
                {
                    "channel": "email",
                    "objective": "Drive checklist downloads",
                    "content_types": ["email"],
                },
                {
                    "channel": "linkedin",
                    "objective": "Reach professional caregivers",
                    "content_types": ["social-post"],
                },
            ],
            "risks": ["Avoid medical claims."],
        },
        policy_verdict="approved",
        policy_confidence=0.91,
    )

    assert isinstance(brief, BriefV1)
    assert brief.artifact_type == "brief.v1"
    assert brief.brand_id == "givecare.brand.core"
    assert brief.lineage is not None
    assert brief.lineage.source_voice_pack_id == brief.voice_pack_id
    assert brief.strategy.platforms == ["email", "linkedin"]
    assert (
        "Audience: Family caregivers: Adult children coordinating care from a distance."
        in brief.strategy.angle
    )
    assert "Checklist users complete key planning tasks faster." in brief.signal.evidence
    assert brief.policy.verdict == "approved"
    assert brief.policy.notes == [
        "Avoid medical claims.",
        "Do not imply guaranteed clinical outcomes.",
    ]
    assert brief.creative.deliverables[0].kind == "email"
    assert "pillar: Relief through preparation" in (brief.creative.deliverables[0].notes or "")


def test_build_brief_v1_ingests_minimal_voice_pack_fixture(monkeypatch):
    monkeypatch.setattr(
        "agentcy.brand.plan.brief_v1.load_brand_profile",
        lambda brand: _Profile(tone="steady", platforms={"email": {}}),
    )

    voice_pack = load_voice_pack_v1(PROTOCOLS / "voice_pack.v1.minimal.json")

    brief = build_brief_v1(
        brief="Drive caregiver engagement around fall planning.",
        brand="GiveCare",
        voice_pack_id=None,
        voice_pack=voice_pack,
        campaign_id="givecare.campaign.fall-checkin.2026-04-12",
        research_result={"insights": ["Families feel stress as routines change entering fall."]},
        strategy_result={"positioning": "Frame planning as relief."},
        creative_result={
            "ctas": ["Download the checklist."],
            "headlines": [{"text": "Prepare for fall"}],
            "body_copy": ["A short plan helps."],
        },
        activation_result={"channels": [{"channel": "email", "objective": "Engagement"}]},
    )

    assert brief.voice_pack_id == "givecare.voice.default.v1"
    assert brief.brand_id == "givecare.brand.core"
    assert "warm" in brief.creative.tone_notes
    assert "plainspoken" in brief.creative.tone_notes
    assert "lead with empathy" in brief.creative.tone_notes
    assert "avoid use fear-based urgency" in brief.creative.tone_notes


def test_build_brief_v1_ingests_rich_voice_pack_fixture(monkeypatch):
    monkeypatch.setattr(
        "agentcy.brand.plan.brief_v1.load_brand_profile",
        lambda brand: _Profile(tone="steady", platforms={"email": {}, "linkedin": {}}),
    )

    voice_pack = load_voice_pack_v1(PROTOCOLS / "voice_pack.v1.rich.json")

    brief = build_brief_v1(
        brief="Increase caregiver response to seasonal planning content.",
        brand="GiveCare",
        voice_pack_id="givecare.voice.fall-checkin.v1",
        voice_pack=voice_pack,
        campaign_id="givecare.campaign.fall-checkin.2026-04-12",
        research_result={
            "insights": ["Caregivers want concrete next steps before routines change."],
        },
        strategy_result={"positioning": "Make early planning feel supportive and manageable."},
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
            ]
        },
        policy_verdict="approved",
        policy_confidence=0.94,
    )

    assert brief.voice_pack_id == "givecare.voice.fall-checkin.v1"
    assert brief.strategy.platforms == ["email", "linkedin"]
    assert brief.creative.tone_notes[:2] == ["actionable", "warm"]
    assert "empathetic" in brief.creative.tone_notes
    assert "non-judgmental" in brief.creative.tone_notes
    assert "offer one concrete next step" in brief.creative.tone_notes
    assert "avoid sound clinical or robotic" in brief.creative.tone_notes


def test_build_brief_v1_handles_empty_sources_list(monkeypatch):
    monkeypatch.setattr(
        "agentcy.brand.plan.brief_v1.load_brand_profile",
        lambda brand: _Profile(tone="steady", platforms={"email": {}}),
    )

    brief = build_brief_v1(
        brief="Launch an employer caregiving resource.",
        brand="GiveCare",
        voice_pack_id="givecare.voice.default.v1",
        campaign_id="givecare.campaign.employer-resource.2026-04-19",
        research_result={"insights": [], "sources": []},
        strategy_result={"positioning": "Caregiving is a workplace issue."},
        creative_result={
            "ctas": ["Review the resource."],
            "headlines": [{"text": "Caregiving at work"}],
            "body_copy": ["Caregiving is a workplace issue."],
        },
        activation_result={"channels": [{"channel": "email", "objective": "Engagement"}]},
    )

    assert brief.signal.source == "planning-input"


def test_build_brief_v1_selectively_rehomes_research_and_strategy_concepts(monkeypatch):
    monkeypatch.setattr(
        "agentcy.brand.plan.brief_v1.load_brand_profile",
        lambda brand: _Profile(tone="clear", platforms={"email": {}, "linkedin": {}}),
    )

    brief = build_brief_v1(
        brief="Launch a practical fall planning campaign for caregivers.",
        brand="GiveCare",
        voice_pack_id="givecare.voice.default.v1",
        campaign_id="givecare.campaign.fall-checkin.2026-04-12",
        research_result={
            "insights": ["Families need one shared planning artifact before routines change."],
            "assumptions": ["Caregivers still trust email for deeper planning guidance."],
            "sources": [
                {
                    "title": "support-call-notes",
                    "url": "https://example.com/support",
                    "snippet": (
                        "Call summaries mention medication, rides, and appointment "
                        "coordination."
                    ),
                }
            ],
        },
        strategy_result={
            "positioning": "Make preparation feel lighter and more doable.",
            "value_proposition": "One shared checklist lowers stress.",
            "target_audience": {
                "name": "Distance caregivers",
                "description": "Adult children coordinating logistics from another city.",
                "pain_points": ["Hard to keep siblings aligned."],
                "motivations": ["Create a calmer plan before an emergency happens."],
            },
            "messaging_pillars": ["Relief through preparation", "Shared family visibility"],
            "proof_points": ["A single checklist helps families align faster."],
            "risks": ["Avoid sounding alarmist."],
        },
        creative_result={
            "headlines": [{"text": "Make fall caregiving feel lighter"}],
            "ctas": ["Download the shared checklist."],
            "body_copy": [],
            "tone_notes": ["warm"],
        },
        activation_result={
            "channels": [
                {
                    "channel": "email",
                    "objective": "Drive checklist downloads",
                    "content_types": ["email"],
                }
            ],
            "risks": ["Avoid medical claims."],
        },
        policy_verdict="approved",
        policy_confidence=0.88,
    )

    assert brief.signal.evidence == [
        "Families need one shared planning artifact before routines change.",
        "Caregivers still trust email for deeper planning guidance.",
        "A single checklist helps families align faster.",
        "support-call-notes (https://example.com/support)",
        "Call summaries mention medication, rides, and appointment coordination.",
    ]
    assert brief.strategy.angle == (
        "Make preparation feel lighter and more doable. | One shared checklist lowers stress. "
        "| Audience: Distance caregivers: Adult children coordinating logistics from another city. "
        "| Pillar: Relief through preparation"
    )
    assert brief.policy.notes == ["Avoid medical claims.", "Avoid sounding alarmist."]
    assert brief.creative.copy_text == (
        "One shared checklist lowers stress. "
        "A single checklist helps families align faster."
    )
    assert brief.creative.deliverables[0].notes == (
        "Drive checklist downloads | pillar: Relief through preparation "
        "| pillar: Shared family visibility | proof: A single checklist helps "
        "families align faster. | audience: Distance caregivers: Adult "
        "children coordinating logistics from another city."
    )


def test_write_brief_v1_emits_schema_shaped_json(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agentcy.brand.plan.brief_v1.load_brand_profile",
        lambda brand: _Profile(tone="clear", platforms={"email": {}}),
    )

    brief = build_brief_v1(
        brief="Drive caregiver engagement around fall planning.",
        brand="GiveCare",
        voice_pack_id="givecare.voice.default.v1",
        campaign_id="givecare.campaign.fall-checkin.2026-04-12",
        research_result={"insights": ["Families feel stress as routines change entering fall."]},
        strategy_result={"positioning": "Frame planning as relief."},
        creative_result={
            "ctas": ["Download the checklist."],
            "headlines": [{"text": "Prepare for fall"}],
            "body_copy": ["A short plan helps."],
            "tone_notes": ["warm"],
        },
        activation_result={"channels": [{"channel": "email", "objective": "Engagement"}]},
    )

    output_path = tmp_path / "brief.v1.json"
    write_brief_v1(output_path, brief)
    payload = json.loads(output_path.read_text())

    assert payload["artifact_type"] == "brief.v1"
    assert payload["writer"] == {"repo": "brand-os", "module": "agentcy-compass"}
    assert payload["voice_pack_id"] == "givecare.voice.default.v1"
    assert payload["lineage"]["source_voice_pack_id"] == "givecare.voice.default.v1"


def test_plan_run_brief_v1_output_smoke_uses_canonical_voice_pack_fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "agentcy.brand.plan.brief_v1.load_brand_profile",
        lambda brand: _Profile(tone="steady", platforms={"email": {}, "linkedin": {}}),
    )

    class _Result:
        def __init__(self, payload):
            self._payload = payload

        def model_dump(self):
            return self._payload

        @property
        def insights(self):
            return self._payload.get("insights", [])

        @property
        def competitors(self):
            return self._payload.get("competitors", [])

        @property
        def positioning(self):
            return self._payload.get("positioning", "")

        @property
        def headlines(self):
            return self._payload.get("headlines", [])

        @property
        def ctas(self):
            return self._payload.get("ctas", [])

        @property
        def channels(self):
            return self._payload.get("channels", [])

        @property
        def calendar(self):
            return self._payload.get("calendar", [])

    monkeypatch.setattr(
        RESEARCH_STAGE,
        "research",
        lambda brief, brand=None: _Result(
            {
                "insights": ["Families want one clear next step before fall gets busy."],
                "competitors": [],
                "assumptions": ["Email drives the highest-intent conversions."],
                "sources": [{"title": "support-call-notes"}],
            }
        ),
    )
    monkeypatch.setattr(
        STRATEGY_STAGE,
        "strategy",
        lambda research_result=None, brief=None, brand=None: _Result(
            {
                "positioning": "Frame planning as relief, not more work.",
                "value_proposition": "A shared checklist lowers caregiver stress.",
            }
        ),
    )
    monkeypatch.setattr(
        CREATIVE_STAGE,
        "creative",
        lambda strategy_result=None, brief=None, brand=None: _Result(
            {
                "headlines": [{"text": "A calmer way to prepare for fall caregiving"}],
                "ctas": ["Download the fall care checklist."],
                "body_copy": [
                    "A short plan today can make the next family decision easier tomorrow."
                ],
                "tone_notes": ["warm", "specific"],
            }
        ),
    )
    monkeypatch.setattr(
        ACTIVATION_STAGE,
        "activation",
        lambda creative_result=None, brief=None, brand=None: _Result(
            {
                "channels": [
                    {
                        "channel": "email",
                        "objective": "Drive checklist downloads",
                        "content_types": ["email"],
                    },
                    {
                        "channel": "linkedin",
                        "objective": "Reach professional caregivers",
                        "content_types": ["social-post"],
                    },
                ],
                "calendar": [],
                "risks": ["Avoid medical claims."],
            }
        ),
    )
    monkeypatch.setattr(
        plan_store,
        "save_campaign",
        lambda brief, brand, stages: "givecare.campaign.fall-checkin.2026-04-12",
    )

    output_path = tmp_path / "brief.v1.json"
    result = runner.invoke(
        app,
        [
            "plan",
            "run",
            "Increase caregiver response to a fall planning checklist.",
            "--brand",
            "GiveCare",
            "--brief-v1-output",
            str(output_path),
            "--voice-pack-input",
            str(PROTOCOLS / "voice_pack.v1.minimal.json"),
            "--policy-verdict",
            "approved",
            "--policy-confidence",
            "0.91",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0, result.stdout
    payload = json.loads(output_path.read_text())
    brief = BriefV1.model_validate(payload)

    assert brief.artifact_type == "brief.v1"
    assert brief.writer.repo == "brand-os"
    assert brief.writer.module == "agentcy-compass"
    assert brief.voice_pack_id == "givecare.voice.default.v1"
    assert brief.lineage is not None
    assert brief.lineage.source_voice_pack_id == brief.voice_pack_id
    assert brief.strategy.platforms == ["email", "linkedin"]
    assert brief.signal.source == "support-call-notes"
    assert brief.policy.verdict == "approved"
    assert brief.creative.deliverables[0].channel == "email"
    assert "brief.v1 saved" in result.stdout
