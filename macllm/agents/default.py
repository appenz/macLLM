from pathlib import Path

import yaml

from macllm.agents.base import MacLLMAgent

_PROMPTS_DIR = Path(__file__).parent / "prompts"
PROMPT_TEMPLATES = yaml.safe_load((_PROMPTS_DIR / "default.yaml").read_text())


class MacLLMDefaultAgent(MacLLMAgent):
    """General-purpose macLLM assistant.

    Instructions are loaded from ``[agents.default]`` in config.toml.
    Prompt templates come from ``macllm/agents/prompts/default.yaml``.
    """

    macllm_name = "default"
    macllm_description = "General-purpose macLLM assistant"
    macllm_tools = [
        "get_current_time",
        "web_search",
        "run_command",
        "read_skill",
        "remember",
    ]
    macllm_managed_agents = ["notes", "calendar", "things", "email"]

    def __init__(self, **kwargs):
        super().__init__(
            prompt_templates=PROMPT_TEMPLATES,
            **kwargs,
        )
