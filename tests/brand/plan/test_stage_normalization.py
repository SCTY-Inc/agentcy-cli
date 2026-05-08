from agentcy.brand.plan.stages.normalize import (
    normalize_activation_result,
    normalize_creative_result,
    normalize_research_result,
    normalize_strategy_result,
)


def test_normalize_research_result_repairs_scalar_and_string_source_fields() -> None:
    payload = normalize_research_result(
        {
            "competitors": [
                {
                    "name": "Vendor A",
                    "positioning": "High-touch support",
                    "strengths": "white glove support; employer reporting",
                    "weaknesses": "higher cost",
                }
            ],
            "sources": ["AP reporting on caregiver benefits"],
            "assumptions": "Employers need concrete policy signals",
        },
        brief="GiveCare launch",
    )

    assert payload["brief"] == "GiveCare launch"
    assert payload["competitors"][0]["strengths"] == [
        "white glove support",
        "employer reporting",
    ]
    assert payload["competitors"][0]["weaknesses"] == ["higher cost"]
    assert payload["sources"][0]["title"] == "AP reporting on caregiver benefits"
    assert payload["assumptions"] == ["Employers need concrete policy signals"]


def test_normalize_strategy_result_repairs_string_segments_and_pillars() -> None:
    payload = normalize_strategy_result(
        {
            "positioning": "Caregiving is a work design issue.",
            "audience": ["HR leaders"],
            "target_audience": "Benefits leaders",
            "pillars": ["Operational caregiving"],
            "messaging_pillars": "Care is infrastructure",
            "proof_points": "63 million Americans are caregivers",
        }
    )

    assert payload["audience"][0]["name"] == "HR leaders"
    assert payload["target_audience"]["name"] == "Benefits leaders"
    assert payload["pillars"][0]["name"] == "Operational caregiving"
    assert payload["messaging_pillars"] == ["Care is infrastructure"]
    assert payload["proof_points"] == ["63 million Americans are caregivers"]


def test_normalize_creative_result_repairs_headlines_and_assets() -> None:
    payload = normalize_creative_result(
        {
            "headlines": ["Caregiving is a workplace issue"],
            "body_copy": "Leave, retention, and work design now meet at caregiving.",
            "assets": ["LinkedIn graphic with one sharp stat"],
        }
    )

    assert payload["headlines"][0]["text"] == "Caregiving is a workplace issue"
    assert payload["body_copy"] == [
        "Leave, retention, and work design now meet at caregiving."
    ]
    assert payload["assets"][0]["description"] == "LinkedIn graphic with one sharp stat"


def test_normalize_activation_result_repairs_channels_calendar_and_kpis() -> None:
    payload = normalize_activation_result(
        {
            "channels": [
                {"channel": "linkedin", "budget_allocation": 40},
            ],
            "calendar": [{"week": 1, "channel": "linkedin", "topic": "launch post"}],
            "kpis": [{"metric": "clicks", "target": 1000}],
            "launch_checklist": "approve final copy",
            "risks": "avoid vague HR jargon",
        }
    )

    assert payload["channels"][0]["channel"] == "linkedin"
    assert payload["channels"][0]["budget_allocation"] == "40"
    assert payload["calendar"][0]["week"] == "1"
    assert payload["calendar"][0]["topic"] == "launch post"
    assert payload["kpis"][0]["metric"] == "clicks"
    assert payload["kpis"][0]["target"] == "1000"
    assert payload["launch_checklist"] == ["approve final copy"]
    assert payload["risks"] == ["avoid vague HR jargon"]
