from types import SimpleNamespace

from macllm.agents import base
from macllm.agents.calendar_agent import CalendarAgent
from macllm.agents.default import MacLLMDefaultAgent
from macllm.agents.lazy_managed import LazyManagedMacLLMAgent
from macllm.core.config import AgentConfig, MacLLMConfig
from macllm.core.chat_history import Conversation


class DummyModel:
    model_id = "dummy"
    api_key = None
    api_base = None


def _patch_agent_environment(monkeypatch):
    from macllm.core import config, llm_service
    from macllm.macllm import MacLLM

    monkeypatch.setattr(config, "_RUNTIME_CONFIG", MacLLMConfig())
    monkeypatch.setitem(llm_service.MODELS, "normal", DummyModel())
    monkeypatch.setitem(llm_service.MODELS, "fast", DummyModel())
    monkeypatch.setitem(llm_service.MODELS, "slow", DummyModel())
    monkeypatch.setattr(MacLLM, "_instance", None)


def test_interactive_supervising_prompt_has_ask_user(monkeypatch):
    _patch_agent_environment(monkeypatch)

    agent = MacLLMDefaultAgent(speed="normal")

    assert agent.planning_interval == 1
    assert "You are an interactive assistant" in agent.system_prompt
    assert "use the ask_user tool to ask the user" in agent.system_prompt
    assert "ask_user:" in agent.system_prompt
    assert "first unchecked item" in agent.system_prompt


def test_plan_update_keeps_latest_checklist(monkeypatch):
    _patch_agent_environment(monkeypatch)
    agent = MacLLMDefaultAgent(speed="normal")

    class Step:
        def __init__(self, name):
            self.name = name
            self.summary_modes = []

        def to_messages(self, summary_mode=False):
            self.summary_modes.append(summary_mode)
            return [self.name]

    class Plan(Step):
        def to_messages(self, summary_mode=False):
            self.summary_modes.append(summary_mode)
            return [] if summary_mode else [self.name]

    monkeypatch.setattr(base, "PlanningStep", Plan)
    system, old, action, latest = (
        Step("system"), Plan("old"), Step("action"), Plan("latest")
    )
    agent.memory = SimpleNamespace(
        system_prompt=system,
        steps=[old, action, latest],
    )
    agent._updating_plan = True

    assert agent.write_memory_to_messages(summary_mode=True) == [
        "system", "action", "latest"
    ]
    assert old.summary_modes == [True]
    assert latest.summary_modes == [False]


def test_parent_plans_require_compact_activity_updates(monkeypatch):
    _patch_agent_environment(monkeypatch)
    agent = MacLLMDefaultAgent(speed="normal")
    planning = agent.prompt_templates["planning"]

    assert "one `<update>…</update>`, then `<end_plan>`" in planning["initial_plan"]
    assert "<update>Checking search results for Guido's personal domain</update>" in planning["initial_plan"]
    assert "one fresh `<update>…</update>`" in planning["update_plan_post_messages"]
    assert "<update>" not in agent.prompt_templates["subagent_system_prompt"]


def test_instructions_and_skills_are_explicit_in_all_prompts(monkeypatch):
    _patch_agent_environment(monkeypatch)
    from macllm.core import config
    from macllm.core.skills import SkillsRegistry

    debug_messages = []
    monkeypatch.setattr(
        base.MacLLMAgent, "_debug", staticmethod(debug_messages.append)
    )
    config._RUNTIME_CONFIG.agents["default"] = AgentConfig(
        instructions="Use the configured workflow."
    )
    monkeypatch.setattr(
        SkillsRegistry,
        "model_catalog_text",
        classmethod(lambda cls, names=None: "- workflow: Follow the workflow."),
    )

    agent = MacLLMDefaultAgent(speed="normal")
    initial = agent.prompt_templates["planning"]["initial_plan"]
    update = agent.prompt_templates["planning"]["update_plan_pre_messages"]

    assert "# Custom Instructions\nUse the configured workflow." in agent.system_prompt
    assert "# Skills\n- workflow: Follow the workflow." in agent.system_prompt
    assert "Use the configured workflow." in initial
    assert "Follow the workflow." in initial
    assert "Use the configured workflow." in update
    assert "Follow the workflow." in update
    assert agent.instructions.startswith("Use the configured workflow.")
    assert "Filesystem: use absolute virtual paths" in agent.instructions
    assert "[agent:default] skills catalog included in system prompt" in debug_messages


def test_task_runner_prompt_has_no_ask_user(monkeypatch):
    _patch_agent_environment(monkeypatch)

    agent = MacLLMDefaultAgent(speed="normal", task_mode=True)

    assert "You are an autonomous task runner" in agent.system_prompt
    assert "Never combine two items from the plan" in agent.system_prompt
    assert "ask_user" not in agent.system_prompt
    assert "ask_user" not in agent.tools


def test_subagent_prompt_is_specialist_prompt(monkeypatch):
    _patch_agent_environment(monkeypatch)

    agent = CalendarAgent(speed="normal", managed_mode=True)

    assert "You are a specialist agent working for a supervising agent" in agent.system_prompt
    assert "Use final_answer to report back to the supervising agent" in agent.system_prompt
    assert "You are an interactive assistant" not in agent.system_prompt
    assert "You can also give tasks to subagents" not in agent.system_prompt
    assert "ask_user tool" not in agent.system_prompt
    assert "ask_user" not in agent.tools


def test_lazy_managed_agent_materializes_managed_prompt(monkeypatch):
    _patch_agent_environment(monkeypatch)
    conversation = Conversation()

    lazy = LazyManagedMacLLMAgent(
        "calendar",
        speed="normal",
        conversation=conversation,
    )

    impl = lazy._materialize()

    assert isinstance(impl, CalendarAgent)
    assert impl._managed_mode is True
    assert impl.planning_interval is None
    assert "You are a specialist agent working for a supervising agent" in impl.system_prompt
