from macllm.agents.base import MacLLMAgent


class MacLLMSmolAgent(MacLLMAgent):
    """Alternate top-level agent; same macLLM prompt YAML as ``default`` (via base default)."""

    macllm_name = "smolagent"
    macllm_description = "Alternate top-level assistant (lighter tool set than default)"
    macllm_tools = [
        "web_search",
        "web_fetch",
        "read_clipboard",
        "read_file",
        "read_skill",
        "ask_user",
    ]
    macllm_managed_agents = ["notes"]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
