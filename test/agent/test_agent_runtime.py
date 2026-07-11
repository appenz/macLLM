from unittest.mock import MagicMock

import pytest

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
