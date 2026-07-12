from macllm.agents.base import MacLLMAgent
from macllm.agents.macllm_prompt_templates import MACLLM_AGENT_PROMPT_TEMPLATES
from macllm.tools.filesystem import FILESYSTEM_TOOLS

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
        "web_fetch",
        "read_clipboard",
        *FILESYSTEM_TOOLS,
        "search_notes",
        "run_command",
        "ask_user",
    ]
    macllm_managed_agents = ["calendar", "things", "email"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
