from macllm.agents.base import MacLLMAgent


class MacLLMSmolAgent(MacLLMAgent):
    """Agent using the upstream smolagents default system prompt templates.

    Passes ``prompt_templates=None`` so smolagents applies its own built-in
    templates.  Uses the same instructions as default (via ``[agents.smolagent]``
    or ``[agents.default]`` in config.toml).
    """

    macllm_name = "smolagent"
    macllm_description = "Agent using the default smolagents system prompt"
    macllm_tools = [
        "get_current_time",
        "web_search",
        "read_skill",
    ]
    macllm_managed_agents = ["notes"]

    def __init__(self, **kwargs):
        super().__init__(
            prompt_templates=None,
            **kwargs,
        )
