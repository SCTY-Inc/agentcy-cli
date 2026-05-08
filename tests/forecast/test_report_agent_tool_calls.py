from __future__ import annotations

import pytest

from agentcy.forecast.services.report_agent import ReportAgent


class _DummyLLM:
    def __init__(self, chat_response: str = "assistant reply", chat_json_error: Exception | None = None):
        self.chat_response = chat_response
        self.chat_json_error = chat_json_error

    def chat(self, *args, **kwargs):
        del args, kwargs
        return self.chat_response

    def chat_json(self, *args, **kwargs):
        del args, kwargs
        if self.chat_json_error is not None:
            raise self.chat_json_error
        return {
            "title": "Predicted Response",
            "summary": "Summary",
            "sections": [{"title": "Actors"}, {"title": "Risks"}],
        }


class _TextResult:
    def __init__(self, text: str):
        self._text = text

    def to_text(self) -> str:
        return self._text


class _Node:
    def __init__(self, name: str):
        self.name = name

    def to_dict(self):
        return {"name": self.name}


class _GraphTools:
    def get_simulation_context(self, **kwargs):
        del kwargs
        return {
            "graph_statistics": {"total_nodes": 2, "total_edges": 1, "entity_types": {"Person": 2}},
            "total_entities": 2,
            "related_facts": [],
        }

    def get_all_nodes(self, graph_id):
        del graph_id
        return []

    def insight_forge(self, **kwargs):
        return _TextResult(f"forge:{kwargs['query']}")

    def panorama_search(self, **kwargs):
        return _TextResult(f"panorama:{kwargs['query']}")

    def quick_search(self, **kwargs):
        return _TextResult(f"quick:{kwargs['query']}:{kwargs['limit']}")

    def interview_agents(self, **kwargs):
        return _TextResult(f"interview:{kwargs['max_agents']}")

    def get_graph_statistics(self, graph_id):
        return {"graph_id": graph_id, "total_nodes": 2}

    def get_entity_summary(self, graph_id, entity_name):
        return {"graph_id": graph_id, "entity_name": entity_name}

    def get_entities_by_type(self, graph_id, entity_type):
        return [_Node(f"{graph_id}:{entity_type}")]



def make_agent(
    *,
    llm: _DummyLLM | None = None,
    graph_tools: _GraphTools | None = None,
) -> ReportAgent:
    return ReportAgent(
        graph_id="graph-demo",
        simulation_id="sim-demo",
        simulation_requirement="Predict reaction",
        llm_client=llm or _DummyLLM(),
        graph_tools=graph_tools or _GraphTools(),
    )



def test_parse_tool_calls_supports_xml_and_bare_json():
    agent = make_agent()

    xml_calls = agent._parse_tool_calls(
        '<tool_call>{"name":"quick_search","parameters":{"query":"care","limit":3}}</tool_call>'
    )
    bare_calls = agent._parse_tool_calls(
        '{"tool":"interview_agents","params":{"query":"care","max_agents":4}}'
    )

    assert xml_calls == [{"name": "quick_search", "parameters": {"query": "care", "limit": 3}}]
    assert bare_calls == [{"name": "interview_agents", "parameters": {"query": "care", "max_agents": 4}}]



def test_execute_tool_redirects_legacy_names_to_current_handlers():
    agent = make_agent()

    assert agent._execute_tool("search_graph", {"query": "care", "limit": "2"}) == "quick:care:2"
    assert agent._execute_tool("get_simulation_context", {"query": "care"}) == "forge:care"


def test_plan_outline_returns_default_outline_on_llm_failure():
    agent = make_agent(llm=_DummyLLM(chat_json_error=ValueError("bad json")))

    outline = agent.plan_outline()

    assert outline.title == "Future Prediction Report"
    assert [section.title for section in outline.sections] == [
        "Prediction Scenario and Core Findings",
        "Population Behavior Prediction Analysis",
        "Trend Outlook and Risk Alerts",
    ]


def test_chat_ignores_report_lookup_failure(monkeypatch: pytest.MonkeyPatch):
    agent = make_agent(llm=_DummyLLM(chat_response="hello from report agent"))
    monkeypatch.setattr(
        "agentcy.forecast.services.report_agent.ReportManager.get_report_by_simulation",
        lambda _simulation_id: (_ for _ in ()).throw(OSError("report store unavailable")),
    )

    result = agent.chat("What happened?")

    assert result["response"] == "hello from report agent"
    assert result["tool_calls"] == []
