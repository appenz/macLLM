"""Lazy managed subagents + /passnote expansion (see Makefile target test-skill-passnote)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from macllm.agents.default import MacLLMDefaultAgent
from macllm.agents.lazy_managed import LazyManagedMacLLMAgent
from macllm.core import llm_service
from macllm.core.skills import SkillsRegistry, _parse_skills_from_markdown

PASSNOTE_MARKER = "PASSNOTE_MAKEFILE_VERIFICATION_MARKER"
FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "skills" / "passnote.md"


class TestLazyManagedSubagents:
    def test_default_agent_wraps_managed_as_lazy(self):
        mock_model = MagicMock()
        mock_model.model_id = "mock-model"
        old = llm_service.MODELS.get("normal")
        llm_service.MODELS["normal"] = mock_model
        try:
            agent = MacLLMDefaultAgent(speed="normal", conversation=None)
            calendar = agent.managed_agents["calendar"]
            assert isinstance(calendar, LazyManagedMacLLMAgent)
            assert calendar._impl is None
        finally:
            llm_service.MODELS["normal"] = old


class TestPassnoteExpansion:
    @pytest.fixture(autouse=True)
    def registry(self):
        text = FIXTURE.read_text(encoding="utf-8")
        parsed = _parse_skills_from_markdown(text, str(FIXTURE))
        assert len(parsed) == 1
        assert parsed[0].name == "passnote"
        SkillsRegistry._skills = {parsed[0].name: parsed[0]}
        SkillsRegistry._loaded = True
        SkillsRegistry._errors = []
        yield
        SkillsRegistry._skills = {}
        SkillsRegistry._loaded = False
        SkillsRegistry._errors = []

    def test_fixture_skill_parses(self):
        assert PASSNOTE_MARKER in SkillsRegistry.get("passnote").body

    def test_expand_passnote_puts_body_in_prompt(self):
        out = SkillsRegistry.expand_manual_invocation("/passnote hello")
        assert PASSNOTE_MARKER in out
        assert "ARGUMENTS: hello" in out
