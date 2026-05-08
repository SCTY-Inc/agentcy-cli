from __future__ import annotations

from agentcy.brand.core.decision import (
    Decision,
    DecisionStatus,
    DecisionType,
    get_decision,
)
from agentcy.brand.workflows.approval import (
    ApprovalWorkflow,
    approve_decision,
    execute_decision,
    reject_decision,
    submit_for_review,
)


def reset_decision_log(monkeypatch) -> None:
    monkeypatch.setattr("agentcy.brand.core.decision._default_log", None)


def test_approval_workflow_persists_review_and_execution(tmp_path, monkeypatch):
    monkeypatch.setenv("BRANDOS_DATA_DIR", str(tmp_path))
    reset_decision_log(monkeypatch)

    decision = Decision(
        id="decision-approve",
        type=DecisionType.SIGNAL_ACTION,
        brand="acme",
        proposal={"action": "observe"},
        rationale="Track the signal and keep an audit trail.",
        confidence=0.82,
    )

    submit_for_review(decision)
    approved = approve_decision(decision.id, reviewer="ops", reason="Looks good")
    executed = execute_decision(decision.id, outcome={"status": "written"})

    assert approved is not None
    assert executed is not None
    assert get_decision(decision.id) is not None
    assert executed.status == DecisionStatus.EXECUTED
    assert executed.reviewer == "ops"
    assert executed.review_reason == "Looks good"
    assert executed.outcome == {"status": "written"}
    assert executed.executed_at is not None


def test_approval_workflow_rejects_invalid_transition(tmp_path, monkeypatch):
    monkeypatch.setenv("BRANDOS_DATA_DIR", str(tmp_path))
    reset_decision_log(monkeypatch)

    decision = Decision(
        id="decision-invalid",
        type=DecisionType.SIGNAL_ACTION,
        brand="acme",
        proposal={"action": "observe"},
        rationale="Track the signal and keep an audit trail.",
        confidence=0.82,
    )

    workflow = ApprovalWorkflow(decision)

    try:
        workflow.approve(reviewer="ops", reason="skip review")
    except ValueError as exc:
        assert "Invalid transition" in str(exc)
    else:  # pragma: no cover - defensive assertion for the test itself
        raise AssertionError("approve() should fail before submit_for_review()")


def test_reject_decision_updates_review_metadata(tmp_path, monkeypatch):
    monkeypatch.setenv("BRANDOS_DATA_DIR", str(tmp_path))
    reset_decision_log(monkeypatch)

    decision = Decision(
        id="decision-reject",
        type=DecisionType.ALERT_ESCALATION,
        brand="acme",
        proposal={"action": "page_operator"},
        rationale="Escalation must be reviewed by a human.",
        confidence=0.91,
    )

    submit_for_review(decision)
    rejected = reject_decision(decision.id, reviewer="ops", reason="Need more context")

    assert rejected is not None
    assert rejected.status == DecisionStatus.REJECTED
    assert rejected.reviewer == "ops"
    assert rejected.review_reason == "Need more context"
    assert rejected.reviewed_at is not None
