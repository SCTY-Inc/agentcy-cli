from __future__ import annotations

import pytest

from agentcy.brand.core.decision import Decision, DecisionStatus, DecisionType
from agentcy.brand.core.policy import BrandPolicy, PolicyEvaluation, PolicyVerdict
from agentcy.brand.loop import AutonomousLoop, LoopConfig


@pytest.mark.asyncio
async def test_unimplemented_autonomous_execution_escalates_instead_of_marking_executed(monkeypatch):
    loop = AutonomousLoop(LoopConfig(max_decisions_per_cycle=1, max_executions_per_cycle=1))
    decision = Decision(
        id="decision-loop",
        type=DecisionType.CONTENT_PUBLISH,
        brand="acme",
        proposal={"action": "publish"},
        rationale="Publish the prepared content.",
        confidence=0.9,
    )
    policy = BrandPolicy(brand="acme")
    evaluation = PolicyEvaluation(
        decision_id=decision.id,
        brand=decision.brand,
        verdict=PolicyVerdict.ALLOW,
        rule_matched="allow-content",
        reasons=["confidence ok"],
    )

    monkeypatch.setattr(loop.policy_engine, "evaluate", lambda *_args, **_kwargs: evaluation)
    monkeypatch.setattr("agentcy.brand.loop.list_decisions", lambda **_kwargs: [])
    monkeypatch.setattr("agentcy.brand.loop.log_outcome", lambda _decision: None)
    monkeypatch.setattr(loop.decision_log, "update", lambda _decision: _decision)

    escalations: list[str | None] = []

    async def fake_escalate(decision, evaluation, extra_reason=None):
        del evaluation
        decision.status = DecisionStatus.PENDING_REVIEW
        decision.review_reason = extra_reason
        escalations.append(extra_reason)

    monkeypatch.setattr(loop, "_escalate_decision", fake_escalate)

    await loop._process_decisions([decision], policy)

    assert decision.status == DecisionStatus.PENDING_REVIEW
    assert loop.state.decisions_executed == 0
    assert loop.state.decisions_escalated == 1
    assert escalations == ["Autonomous content_publish execution is not implemented"]
