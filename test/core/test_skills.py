"""Tests for SkillsRegistry: filtered catalog and user-invocable flag."""

import pytest

from macllm.core import config as config_mod
from macllm.core.config import FilesystemConfig, FilesystemMountConfig, MacLLMConfig
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


def test_reload_discovers_skills_from_filesystem_mount(tmp_path, monkeypatch):
    skill_file = tmp_path / "mounted.md"
    skill_file.write_text(
        "---\nname: mounted\ndescription: Mounted skill\n---\nInstructions."
    )
    monkeypatch.setattr(
        config_mod,
        "_RUNTIME_CONFIG",
        MacLLMConfig(
            filesystem=FilesystemConfig({
                "test_skills": FilesystemMountConfig(
                    "/skills/test",
                    str(tmp_path),
                    "read-only",
                    "read-only",
                    False,
                )
            })
        ),
    )

    SkillsRegistry.reload()

    assert SkillsRegistry.get("mounted") is not None
    assert "/skills/test/mounted.md" in SkillsRegistry.model_catalog_text()


class TestFilteredCatalog:
    @pytest.fixture(autouse=True)
    def setup_registry(self, monkeypatch):
        monkeypatch.setattr(
            "macllm.core.skills.skill_virtual_path",
            lambda source: "/skills/test/skills.md",
        )
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

    def test_expand_manual_invocation_works_inside_prompt(self):
        result = SkillsRegistry.expand_manual_invocation("Please use /public here")
        assert result == "Please use body here"

    def test_expand_manual_invocation_works_at_end_of_prompt(self):
        result = SkillsRegistry.expand_manual_invocation("Please use /public")
        assert result == "Please use body"

    def test_expand_manual_invocation_expands_skills_in_leading_args(self):
        SkillsRegistry._skills["other"] = _make_skill("other", body="other body")
        result = SkillsRegistry.expand_manual_invocation("/public then /other")
        assert "body" in result
        assert "ARGUMENTS: then other body" in result

    def test_expand_manual_invocation_blocked_for_non_user_invocable(self):
        result = SkillsRegistry.expand_manual_invocation("/agent-only some args")
        assert result == "/agent-only some args"

    def test_model_invocable_unaffected_by_user_invocable(self):
        skill = SkillsRegistry.get_model_invocable("agent-only")
        assert skill is not None
        assert skill.name == "agent-only"


class TestDuplicateSkillNames:
    def test_duplicate_in_same_file_raises(self):
        md = (
            "---\nname: dup\ndescription: a\n---\nA\n"
            "---\nname: dup\ndescription: b\n---\nB\n"
        )
        with pytest.raises(ValueError, match="Duplicate skill name 'dup'"):
            _parse_skills_from_markdown(md, "/t.md")


class TestPackSkillMdFallback:
    """SKILL.md may omit name:; folder name is used (Cursor-style packs)."""

    def test_uses_pack_directory_name_when_name_missing(self):
        md = "---\ndescription: Agent for notes\n---\nDo the thing.\n"
        skills = _parse_skills_from_markdown(
            md, "/skills/notes-agent/SKILL.md", pack_directory_name="notes-agent"
        )
        assert len(skills) == 1
        assert skills[0].name == "notes-agent"
        assert skills[0].description == "Agent for notes"
        assert "Do the thing." in skills[0].body

    def test_missing_name_emits_debug_warning(self, monkeypatch):
        logged: list[tuple[str, int]] = []

        def capture(msg: str, level: int = 0):
            logged.append((msg, level))

        monkeypatch.setattr("macllm.core.skills._skills_debug_log", capture)
        md = "---\ndescription: x\n---\nbody\n"
        _parse_skills_from_markdown(
            md, "/p/SKILL.md", pack_directory_name="packdir"
        )
        assert logged
        assert any("no name:" in m[0] and m[1] == 3 for m in logged)

    def test_explicit_name_in_pack_does_not_warn(self, monkeypatch):
        logged: list[tuple[str, int]] = []

        def capture(msg: str, level: int = 0):
            logged.append((msg, level))

        monkeypatch.setattr("macllm.core.skills._skills_debug_log", capture)
        md = "---\nname: myskill\ndescription: x\n---\nbody\n"
        skills = _parse_skills_from_markdown(
            md, "/p/SKILL.md", pack_directory_name="packdir"
        )
        assert skills[0].name == "myskill"
        assert not any("no name:" in m[0] for m in logged)


class TestSkillMarkdownBoundaries:
    """--- in body must not split skills unless the block declares name:."""

    def test_horizontal_rule_in_body_keeps_one_skill(self):
        md = (
            "---\nname: passnote\ndescription: Test\n---\n"
            "Intro line\n\n"
            "---\n\n"
            "## Section\nRest of skill"
        )
        skills = _parse_skills_from_markdown(md, "/passnote.md")
        assert len(skills) == 1
        assert skills[0].name == "passnote"
        assert "Intro line" in skills[0].body
        assert "## Section" in skills[0].body
        assert "Rest of skill" in skills[0].body

    def test_multiple_named_blocks_still_split(self):
        md = (
            "---\nname: a\ndescription: x\n---\nBody A\n"
            "---\nname: b\ndescription: y\n---\nBody B"
        )
        skills = _parse_skills_from_markdown(md, "/two.md")
        assert len(skills) == 2
        assert skills[0].name == "a"
        assert skills[0].body.strip() == "Body A"
        assert skills[1].name == "b"
        assert skills[1].body.strip() == "Body B"


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


class _SpeedPrefixes:
    def get_prefixes(self):
        return ["/fast", "/slow", "/think"]


class TestFailedLeadingSlash:
    """Leading /command that is not a skill, builtin, or plugin slash → error message."""

    def test_unknown_skill_returns_message(self):
        SkillsRegistry._skills = {}
        SkillsRegistry._loaded = True
        try:
            msg = SkillsRegistry.failed_leading_slash_skill_message(
                "/passnote x", "/passnote x", [_SpeedPrefixes()]
            )
            assert msg is not None
            assert "passnote" in msg.lower()
        finally:
            SkillsRegistry._skills = {}
            SkillsRegistry._loaded = False

    def test_plugin_slash_no_message(self):
        SkillsRegistry._skills = {}
        SkillsRegistry._loaded = True
        try:
            assert (
                SkillsRegistry.failed_leading_slash_skill_message(
                    "/fast", "/fast", [_SpeedPrefixes()]
                )
                is None
            )
            assert (
                SkillsRegistry.failed_leading_slash_skill_message(
                    "/reload", "/reload", []
                )
                is None
            )
        finally:
            SkillsRegistry._skills = {}
            SkillsRegistry._loaded = False

    def test_non_user_invocable_message(self):
        SkillsRegistry._skills = {
            "agent-only": _make_skill("agent-only", user_invocable=False),
        }
        SkillsRegistry._loaded = True
        try:
            msg = SkillsRegistry.failed_leading_slash_skill_message(
                "/agent-only hi", "/agent-only hi", []
            )
            assert msg is not None
            assert "user-invocable" in msg.lower()
        finally:
            SkillsRegistry._skills = {}
            SkillsRegistry._loaded = False

    def test_expanded_skill_no_message(self):
        SkillsRegistry._skills = {"public": _make_skill("public", user_invocable=True)}
        SkillsRegistry._loaded = True
        try:
            expanded = SkillsRegistry.expand_manual_invocation("/public a")
            assert expanded != "/public a"
            assert (
                SkillsRegistry.failed_leading_slash_skill_message(
                    "/public a", expanded, []
                )
                is None
            )
        finally:
            SkillsRegistry._skills = {}
            SkillsRegistry._loaded = False

    def test_plain_text_no_message(self):
        assert (
            SkillsRegistry.failed_leading_slash_skill_message("hello", "hello", [])
            is None
        )

    def test_empty_skill_body_shows_message(self):
        SkillsRegistry._skills = {"empty": _make_skill("empty", body="")}
        SkillsRegistry._loaded = True
        try:
            assert SkillsRegistry.expand_manual_invocation("/empty") == "/empty"
            msg = SkillsRegistry.failed_leading_slash_skill_message(
                "/empty", "/empty", []
            )
            assert msg is not None
            assert "empty" in msg.lower()
        finally:
            SkillsRegistry._skills = {}
            SkillsRegistry._loaded = False
