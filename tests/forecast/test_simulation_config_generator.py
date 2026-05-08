from __future__ import annotations

from agentcy.forecast.services.entity_reader import EntityNode
from agentcy.forecast.services.simulation_config_generator import (
    AgentActivityConfig,
    EventConfig,
    SimulationConfigGenerator,
)


def _entity(name: str, entity_type: str, summary: str = "") -> EntityNode:
    return EntityNode(
        uuid=f"uuid-{name}",
        name=name,
        labels=["Entity", entity_type],
        summary=summary or f"{name} reacts to the policy update.",
        attributes={},
    )


def test_parse_event_config_promotes_scenario_buckets_into_seed_posts_and_followups() -> None:
    generator = SimulationConfigGenerator(provider="codex-cli")

    event_config = generator._parse_event_config(
        {
            "hot_topics": ["caregiver relief"],
            "narrative_direction": "Relief enthusiasm competes with durability concerns.",
            "scenario_buckets": [
                {
                    "label": "Practical relief",
                    "focus": "Families focus on immediate help.",
                    "poster_type": "Student",
                    "seed_post": "This could finally make caregiving easier week to week.",
                    "follow_up": "People ask whether the support lasts beyond the pilot.",
                    "trigger_round": 2,
                    "topics": ["caregiver relief", "pilot durability"],
                }
            ],
        },
        simulation_requirement="Predict reaction to a caregiver relief pilot",
        entities=[_entity("Caregiver", "Student"), _entity("Local News", "MediaOutlet")],
    )

    assert event_config.scenario_buckets[0]["bucket_id"] == "practical-relief"
    assert event_config.initial_posts[0]["content"] == (
        "This could finally make caregiving easier week to week."
    )
    assert event_config.initial_posts[0]["scenario_bucket_id"] == "practical-relief"
    assert event_config.initial_posts[0]["scenario_bucket_label"] == "Practical relief"
    assert event_config.scheduled_events[0]["trigger_round"] == 2
    assert "pilot durability" in event_config.hot_topics


def test_parse_event_config_builds_fallback_taxonomy_buckets_when_llm_output_is_sparse() -> None:
    generator = SimulationConfigGenerator(provider="codex-cli")

    event_config = generator._parse_event_config(
        {"narrative_direction": "Mixed reaction."},
        simulation_requirement="Predict reaction to caregiver relief pilot for employers and families",
        entities=[
            _entity("Caregiver", "Student"),
            _entity("City Health", "University"),
            _entity("Regional News", "MediaOutlet"),
        ],
    )

    assert event_config.scenario_buckets
    assert event_config.initial_posts
    assert len(event_config.initial_posts) == len(event_config.scenario_buckets)
    assert all(post.get("poster_type") for post in event_config.initial_posts)
    assert any(bucket.get("topics") for bucket in event_config.scenario_buckets)


def test_assign_initial_post_agents_preserves_scenario_bucket_metadata() -> None:
    generator = SimulationConfigGenerator(provider="codex-cli")
    event_config = EventConfig(
        initial_posts=[
            {
                "content": "Caregivers need immediate relief.",
                "poster_type": "Student",
                "scenario_bucket_id": "practical-relief",
                "scenario_bucket_label": "Practical relief",
            }
        ]
    )

    assigned = generator._assign_initial_post_agents(
        event_config,
        [
            AgentActivityConfig(
                agent_id=7,
                entity_uuid="entity-7",
                entity_name="Caregiver",
                entity_type="Student",
            )
        ],
    )

    assert assigned.initial_posts[0]["poster_agent_id"] == 7
    assert assigned.initial_posts[0]["scenario_bucket_id"] == "practical-relief"
    assert assigned.initial_posts[0]["scenario_bucket_label"] == "Practical relief"
