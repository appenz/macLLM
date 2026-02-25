from unittest.mock import Mock

from macllm.tags.agent_tag import AgentTag
from macllm.core.user_request import UserRequest


class TestAgentTagExpand:
    def setup_method(self):
        self.tag = AgentTag(macllm=Mock())

    def test_sets_agent_name(self):
        request = UserRequest("hello @agent:smolagent world")
        self.tag.expand("@agent:smolagent", Mock(), request)
        assert request.agent_name == "smolagent"

    def test_returns_empty_string(self):
        request = UserRequest("test")
        result = self.tag.expand("@agent:default", Mock(), request)
        assert result == ""

    def test_unknown_agent_falls_back_to_default(self):
        request = UserRequest("test")
        self.tag.expand("@agent:nonexistent_xyz", Mock(), request)
        assert request.agent_name == "default"

    def test_prefixes(self):
        assert "@agent:" in self.tag.get_prefixes()


class TestAgentTagAutocomplete:
    def setup_method(self):
        self.tag = AgentTag(macllm=Mock())

    def test_autocomplete_returns_matches(self):
        results = self.tag.autocomplete("@agent:")
        assert any("default" in r for r in results)
        assert any("smolagent" in r for r in results)

    def test_autocomplete_filters(self):
        results = self.tag.autocomplete("@agent:d")
        assert any("default" in r for r in results)
        assert not any("smolagent" in r for r in results)

    def test_autocomplete_non_matching_prefix(self):
        results = self.tag.autocomplete("@file:")
        assert results == []

    def test_supports_autocomplete(self):
        assert self.tag.supports_autocomplete() is True
