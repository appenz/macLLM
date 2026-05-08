from macllm.agents.base import MacLLMAgent
from macllm.agents.macllm_prompt_templates import MACLLM_AGENT_PROMPT_TEMPLATES

# Backwards-compatible name for callers/tests.
PROMPT_TEMPLATES = MACLLM_AGENT_PROMPT_TEMPLATES


class MacLLMDefaultAgent(MacLLMAgent):
    """General-purpose macLLM assistant.

    Instructions are loaded from ``[agents.default]`` in config.toml.
    Prompt templates come from ``macllm/agents/prompts/default.yaml``.
    """

    macllm_name = "default"
    macllm_description = "General-purpose macLLM assistant"
    macllm_tools = [
        "web_search",
        "run_command",
        "read_skill",
        "remember",
    ]
    macllm_managed_agents = ["notes", "calendar", "things", "email"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
