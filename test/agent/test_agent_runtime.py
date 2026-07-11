from unittest.mock import MagicMock

import pytest
from smolagents import ToolCallingAgent

from macllm.agents.default import MacLLMDefaultAgent
from macllm.core import device_context, llm_service
from macllm.core.agent_service import create_agent
from macllm.core.chat_history import Conversation


def _agent(monkeypatch):
    monkeypatch.setitem(llm_service.MODELS, "normal", MagicMock())
    monkeypatch.setattr(device_context, "get_device_context", lambda: "Test situation")
    return create_agent(
        agent_cls=MacLLMDefaultAgent,
        speed="normal",
        conversation=Conversation(),
    )


def test_no_tools_gate_blocks_tool_execution(monkeypatch):
    from smolagents.agents import AgentToolExecutionError

    agent = _agent(monkeypatch)
    agent._tools_disabled = True

    with pytest.raises(AgentToolExecutionError, match="disabled"):
        agent.execute_tool_call("any_tool_or_subagent", {})


def test_no_tools_gate_allows_final_answer(monkeypatch):
    agent = _agent(monkeypatch)
    agent._tools_disabled = True

    result = agent.execute_tool_call("final_answer", {"answer": "done"})

    assert "done" in str(result)


def test_action_marker_precedes_dispatch(monkeypatch):
    agent = _agent(monkeypatch)

    def execute(_self, _name, _arguments):
        marker = agent._conversation.conversation_log[-1]
        assert (marker.kind, marker.payload) == ("action_started", "default")
        return "done"

    monkeypatch.setattr(ToolCallingAgent, "execute_tool_call", execute)
    assert agent.execute_tool_call("anything", {}) == "done"


def test_planning_marker_precedes_model_call(monkeypatch):
    agent = _agent(monkeypatch)

    def generate(_self, _task, _is_first_step, _step):
        marker = agent._conversation.conversation_log[-1]
        assert (marker.kind, marker.payload) == ("planning_started", "default")
        yield "done"

    monkeypatch.setattr(ToolCallingAgent, "_generate_planning_step", generate)
    assert list(agent._generate_planning_step("task", True, object())) == ["done"]
