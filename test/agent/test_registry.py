import pytest

from macllm.agents import (
    get_agent_class,
    get_default_agent_class,
    list_agents,
    AGENT_REGISTRY,
    _discover_agents,
)
from macllm.agents.base import MacLLMAgent
from macllm.agents.default import MacLLMDefaultAgent, CUSTOM_INSTRUCTIONS
from macllm.agents.smolagent import MacLLMSmolAgent


class TestAgentDiscovery:
    def test_registry_populated(self):
        _discover_agents()
        assert len(AGENT_REGISTRY) >= 2

    def test_default_registered(self):
        assert get_agent_class("default") is MacLLMDefaultAgent

    def test_smolagent_registered(self):
        assert get_agent_class("smolagent") is MacLLMSmolAgent

    def test_unknown_raises(self):
        with pytest.raises(KeyError):
            get_agent_class("nonexistent_agent_xyz")

    def test_get_default_agent_class(self):
        cls = get_default_agent_class()
        assert cls is MacLLMDefaultAgent

    def test_list_agents_returns_all(self):
        agents = list_agents()
        names = {a.macllm_name for a in agents}
        assert "default" in names
        assert "smolagent" in names


class TestAgentDefinitions:
    def test_default_agent_attributes(self):
        assert MacLLMDefaultAgent.macllm_name == "default"
        assert CUSTOM_INSTRUCTIONS is not None
        assert len(CUSTOM_INSTRUCTIONS) > 0
        assert "get_current_time" in MacLLMDefaultAgent.macllm_tools
        assert "web_search" in MacLLMDefaultAgent.macllm_tools

    def test_smolagent_attributes(self):
        assert MacLLMSmolAgent.macllm_name == "smolagent"
        assert len(MacLLMSmolAgent.macllm_tools) > 0

    def test_all_agents_inherit_from_base(self):
        for agent_cls in list_agents():
            assert issubclass(agent_cls, MacLLMAgent)

    def test_agent_names_unique(self):
        agents = list_agents()
        names = [a.macllm_name for a in agents]
        assert len(names) == len(set(names))
