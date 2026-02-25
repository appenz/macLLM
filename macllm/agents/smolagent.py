from macllm.agents.base import MacLLMAgent
from macllm.agents.default import CUSTOM_INSTRUCTIONS


class MacLLMSmolAgent(MacLLMAgent):
    """Agent using the upstream smolagents default system prompt templates.

    Passes ``prompt_templates=None`` so smolagents applies its own built-in
    templates.  Uses the same ``custom_instructions`` as MacLLMDefaultAgent.
    """

    macllm_name = "smolagent"
    macllm_description = "Agent using the default smolagents system prompt"
    macllm_tools = [
        "get_current_time",
        "web_search",
        "search_files",
        "read_full_file",
        "file_append",
        "file_create",
    ]

    def __init__(self, **kwargs):
        super().__init__(
            custom_instructions=CUSTOM_INSTRUCTIONS,
            prompt_templates=None,
            **kwargs,
        )
