"""Unit tests for SimulationRunner state machine and AgentAction/RoundSummary models."""

from __future__ import annotations

from agentcy.forecast.services.simulation_runner import AgentAction, RoundSummary, RunnerStatus


class TestRunnerStatus:
    def test_all_terminal_states_present(self):
        terminals = {RunnerStatus.STOPPED, RunnerStatus.COMPLETED, RunnerStatus.FAILED}
        assert all(s in RunnerStatus.__members__.values() for s in terminals)

    def test_string_value_matches_name(self):
        # str enum — RunnerStatus.IDLE == "idle"
        assert RunnerStatus.IDLE == "idle"
        assert RunnerStatus.COMPLETED == "completed"
        assert RunnerStatus.FAILED == "failed"


class TestAgentAction:
    def _make(self, **kwargs) -> AgentAction:
        defaults = dict(
            round_num=1,
            timestamp="2026-01-01T00:00:00Z",
            platform="twitter",
            agent_id=42,
            agent_name="Alice",
            action_type="CREATE_POST",
        )
        defaults.update(kwargs)
        return AgentAction(**defaults)

    def test_to_dict_has_required_keys(self):
        action = self._make()
        d = action.to_dict()
        for key in ("round_num", "timestamp", "platform", "agent_id", "agent_name",
                    "action_type", "action_args", "result", "success"):
            assert key in d

    def test_default_success_is_true(self):
        assert self._make().success is True

    def test_default_action_args_is_empty_dict(self):
        assert self._make().action_args == {}

    def test_default_result_is_none(self):
        assert self._make().result is None

    def test_custom_values_round_trip(self):
        action = self._make(
            action_args={"content": "hello"},
            result="ok",
            success=False,
        )
        d = action.to_dict()
        assert d["action_args"] == {"content": "hello"}
        assert d["result"] == "ok"
        assert d["success"] is False


class TestRoundSummary:
    def _make(self, **kwargs) -> RoundSummary:
        defaults = dict(round_num=1, start_time="2026-01-01T00:00:00Z")
        defaults.update(kwargs)
        return RoundSummary(**defaults)

    def test_defaults(self):
        rs = self._make()
        assert rs.end_time is None
        assert rs.simulated_hour == 0
        assert rs.twitter_actions == 0
        assert rs.reddit_actions == 0
        assert rs.active_agents == []
        assert rs.actions == []

    def test_action_accumulation(self):
        rs = self._make()
        action = AgentAction(
            round_num=1,
            timestamp="2026-01-01T00:00:00Z",
            platform="twitter",
            agent_id=1,
            agent_name="Bot",
            action_type="LIKE_POST",
        )
        rs.actions.append(action)
        assert len(rs.actions) == 1
        assert rs.actions[0].action_type == "LIKE_POST"

    def test_active_agents_independence(self):
        # Mutable default field must not share state between instances
        rs1 = self._make()
        rs2 = self._make()
        rs1.active_agents.append(99)
        assert 99 not in rs2.active_agents
