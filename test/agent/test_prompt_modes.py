from macllm.agents.calendar_agent import CalendarAgent
from macllm.agents.default import MacLLMDefaultAgent
from macllm.agents.lazy_managed import LazyManagedMacLLMAgent
from macllm.agents.note_agent import NoteAgent
from macllm.core.config import MacLLMConfig
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

    assert "You are an interactive assistant" in agent.system_prompt
    assert "use the ask_user tool to ask the user" in agent.system_prompt
    assert "ask_user:" in agent.system_prompt


def test_task_runner_prompt_has_no_ask_user(monkeypatch):
    _patch_agent_environment(monkeypatch)

    agent = MacLLMDefaultAgent(speed="normal", task_mode=True)

    assert "You are an autonomous task runner" in agent.system_prompt
    assert "ask_user" not in agent.system_prompt
    assert "ask_user" not in agent.tools


def test_subagent_prompt_is_specialist_prompt(monkeypatch):
    _patch_agent_environment(monkeypatch)

    agent = NoteAgent(speed="normal", managed_mode=True)

    assert "You are a specialist agent working for a supervising agent" in agent.system_prompt
    assert "Use final_answer to report back to the supervising agent" in agent.system_prompt
    assert "You are an interactive assistant" not in agent.system_prompt
    assert "You can also give tasks to team members" not in agent.system_prompt
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
