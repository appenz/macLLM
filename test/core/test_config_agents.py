"""Tests for per-agent config sections ([agents.*] in config.toml)."""

from macllm.core.config import _from_dict, AgentConfig


class TestAgentConfigDefaults:
    def test_no_agents_section(self):
        config = _from_dict({})
        assert config.agents == {}

    def test_empty_agents_section(self):
        config = _from_dict({"agents": {}})
        assert config.agents == {}

    def test_agent_with_skills(self):
        data = {"agents": {"notes": {"skills": ["organize", "format"]}}}
        config = _from_dict(data)
        assert "notes" in config.agents
        assert config.agents["notes"].skills == ["organize", "format"]
        assert config.agents["notes"].instructions == ""

    def test_agent_with_instructions(self):
        data = {"agents": {"default": {"instructions": "Be helpful."}}}
        config = _from_dict(data)
        assert config.agents["default"].instructions == "Be helpful."
        assert config.agents["default"].skills == []

    def test_agent_with_both(self):
        data = {"agents": {"notes": {
            "skills": ["organize"],
            "instructions": "You manage notes.",
        }}}
        config = _from_dict(data)
        cfg = config.agents["notes"]
        assert cfg.skills == ["organize"]
        assert cfg.instructions == "You manage notes."

    def test_multiple_agents(self):
        data = {"agents": {
            "notes": {"skills": ["a"]},
            "calendar": {"skills": ["b", "c"]},
            "default": {"instructions": "Hello."},
        }}
        config = _from_dict(data)
        assert len(config.agents) == 3
        assert config.agents["notes"].skills == ["a"]
        assert config.agents["calendar"].skills == ["b", "c"]
        assert config.agents["default"].instructions == "Hello."

    def test_non_dict_agent_entry_ignored(self):
        data = {"agents": {"bad": "not a dict", "good": {"skills": ["x"]}}}
        config = _from_dict(data)
        assert "bad" not in config.agents
        assert "good" in config.agents

    def test_agents_none_handled(self):
        data = {"agents": None}
        config = _from_dict(data)
        assert config.agents == {}

    def test_agent_with_preload_skill(self):
        data = {"agents": {"notes": {"preload_skill": "my-notes-prefs"}}}
        config = _from_dict(data)
        assert config.agents["notes"].preload_skill == "my-notes-prefs"

    def test_preload_skill_defaults_empty(self):
        data = {"agents": {"notes": {"skills": ["a"]}}}
        config = _from_dict(data)
        assert config.agents["notes"].preload_skill == ""

    def test_agent_with_all_fields(self):
        data = {"agents": {"notes": {
            "skills": ["organize"],
            "instructions": "Manage notes.",
            "preload_skill": "notes-context",
        }}}
        config = _from_dict(data)
        cfg = config.agents["notes"]
        assert cfg.skills == ["organize"]
        assert cfg.instructions == "Manage notes."
        assert cfg.preload_skill == "notes-context"
