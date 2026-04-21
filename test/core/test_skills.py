"""Tests for SkillsRegistry: filtered catalog and user-invocable flag."""

import pytest

from macllm.core.skills import Skill, SkillsRegistry, _parse_skills_from_markdown


def _make_skill(name, description="desc", disable_model=False,
                user_invocable=True, body="body"):
    return Skill(
        name=name,
        description=description,
        disable_model_invocation=disable_model,
        user_invocable=user_invocable,
        body=body,
        source="/fake/skills.md",
    )


class TestFilteredCatalog:
    @pytest.fixture(autouse=True)
    def setup_registry(self):
        SkillsRegistry._skills = {
            "alpha": _make_skill("alpha", "Alpha skill"),
            "beta": _make_skill("beta", "Beta skill"),
            "gamma": _make_skill("gamma", "Gamma skill"),
            "hidden": _make_skill("hidden", "Hidden", disable_model=True),
        }
        SkillsRegistry._loaded = True
        yield
        SkillsRegistry._skills = {}
        SkillsRegistry._loaded = False

    def test_catalog_unfiltered(self):
        text = SkillsRegistry.model_catalog_text()
        assert "alpha" in text
        assert "beta" in text
        assert "gamma" in text
        assert "hidden" not in text

    def test_catalog_filtered_subset(self):
        text = SkillsRegistry.model_catalog_text(names=["alpha", "gamma"])
        assert "alpha" in text
        assert "gamma" in text
        assert "beta" not in text

    def test_catalog_filtered_empty(self):
        text = SkillsRegistry.model_catalog_text(names=[])
        assert "No model-invocable skills" in text

    def test_catalog_filtered_nonexistent_name(self):
        text = SkillsRegistry.model_catalog_text(names=["nonexistent"])
        assert "No model-invocable skills" in text

    def test_catalog_none_means_all(self):
        text = SkillsRegistry.model_catalog_text(names=None)
        assert "alpha" in text
        assert "beta" in text
        assert "gamma" in text


class TestUserInvocable:
    @pytest.fixture(autouse=True)
    def setup_registry(self):
        SkillsRegistry._skills = {
            "public": _make_skill("public", user_invocable=True),
            "agent-only": _make_skill("agent-only", user_invocable=False),
            "both-hidden": _make_skill("both-hidden", user_invocable=False,
                                       disable_model=True),
        }
        SkillsRegistry._loaded = True
        yield
        SkillsRegistry._skills = {}
        SkillsRegistry._loaded = False

    def test_list_manual_commands_includes_user_invocable(self):
        cmds = SkillsRegistry.list_manual_commands()
        assert "/public" in cmds

    def test_list_manual_commands_excludes_non_user_invocable(self):
        cmds = SkillsRegistry.list_manual_commands()
        assert "/agent-only" not in cmds
        assert "/both-hidden" not in cmds

    def test_expand_manual_invocation_works_for_user_invocable(self):
        result = SkillsRegistry.expand_manual_invocation("/public some args")
        assert "body" in result
        assert "ARGUMENTS: some args" in result

    def test_expand_manual_invocation_blocked_for_non_user_invocable(self):
        result = SkillsRegistry.expand_manual_invocation("/agent-only some args")
        assert result == "/agent-only some args"

    def test_model_invocable_unaffected_by_user_invocable(self):
        skill = SkillsRegistry.get_model_invocable("agent-only")
        assert skill is not None
        assert skill.name == "agent-only"


class TestUserInvocableParsing:
    def test_default_is_true(self):
        md = "---\nname: test\ndescription: A test\n---\nBody here."
        skills = _parse_skills_from_markdown(md, "/test.md")
        assert len(skills) == 1
        assert skills[0].user_invocable is True

    def test_explicit_false(self):
        md = "---\nname: test\ndescription: A test\nuser-invocable: false\n---\nBody."
        skills = _parse_skills_from_markdown(md, "/test.md")
        assert skills[0].user_invocable is False

    def test_explicit_true(self):
        md = "---\nname: test\ndescription: A test\nuser-invocable: true\n---\nBody."
        skills = _parse_skills_from_markdown(md, "/test.md")
        assert skills[0].user_invocable is True

    def test_multi_skill_file_independent_flags(self):
        md = (
            "---\nname: first\ndescription: d\nuser-invocable: false\n---\nBody1\n"
            "---\nname: second\ndescription: d\n---\nBody2\n"
        )
        skills = _parse_skills_from_markdown(md, "/test.md")
        assert len(skills) == 2
        assert skills[0].user_invocable is False
        assert skills[1].user_invocable is True


class TestPreloadSkill:
    """Test that SkillsRegistry.get() returns skills usable for preloading."""

    @pytest.fixture(autouse=True)
    def setup_registry(self):
        SkillsRegistry._skills = {
            "context": _make_skill("context", body="Always use Markdown headers."),
            "model-hidden": _make_skill("model-hidden", disable_model=True,
                                        body="Hidden context."),
        }
        SkillsRegistry._loaded = True
        yield
        SkillsRegistry._skills = {}
        SkillsRegistry._loaded = False

    def test_get_returns_preloadable_skill(self):
        skill = SkillsRegistry.get("context")
        assert skill is not None
        assert skill.body == "Always use Markdown headers."

    def test_get_returns_model_hidden_skill(self):
        """preload_skill uses get(), not get_model_invocable(), so even
        model-hidden skills can be preloaded."""
        skill = SkillsRegistry.get("model-hidden")
        assert skill is not None
        assert skill.body == "Hidden context."

    def test_get_returns_none_for_missing(self):
        assert SkillsRegistry.get("nonexistent") is None
