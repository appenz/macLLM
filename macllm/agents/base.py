from typing import Optional, Callable

import litellm
from smolagents import ToolCallingAgent, LogLevel, PlanningStep, ActionStep, TaskStep

litellm.drop_params = True


class MacLLMAgent(ToolCallingAgent):
    """Base class for all macLLM agents.

    **Identity attributes** (class-level, used by registry / UI / tool resolution):

    - ``macllm_name``        -- identifier for the agent registry and ``@agent:`` tag
    - ``macllm_description`` -- human-readable description (also used for managed agents)
    - ``macllm_tools``       -- list of tool name strings from ``macllm.tools``

    **Behavioural configuration** is passed via bespoke ``__init__`` overrides in
    each subclass.  Subclass constructors call ``super().__init__()`` with any
    combination of smolagents parameters they want to customise:

    - ``custom_instructions`` -- inserted as ``{{custom_instructions}}`` in the
      system prompt template (smolagents' ``instructions`` parameter)
    - ``prompt_templates``    -- full or partial ``PromptTemplates`` dict
    - ``planning_interval``   -- how often the planning step runs

    If a parameter is left at its default (``None`` / ``3``), smolagents' own
    defaults apply.
    """

    macllm_name: str = ""
    macllm_description: str = ""
    macllm_tools: list[str] = []

    def __init__(self, speed: str = "normal",
                 token_callback: Optional[Callable[[int, int], None]] = None,
                 managed_agents: list | None = None,
                 custom_instructions: str | None = None,
                 prompt_templates: dict | None = None,
                 planning_interval: int = 3,
                 **kwargs):
        from macllm.core.llm_service import MODELS
        from macllm import tools as tools_module
        from macllm.core.agent_service import create_step_callback
        from macllm.tools.web_search import reset_search_counter

        reset_search_counter()

        model = MODELS.get(speed.lower(), MODELS['normal'])
        if model is None:
            raise ValueError(f"Model for speed '{speed}' is not configured (missing API key)")

        tools = [getattr(tools_module, n) for n in self.macllm_tools]
        step_callback = create_step_callback(token_callback)

        super().__init__(
            tools=tools,
            model=model,
            instructions=custom_instructions,
            prompt_templates=prompt_templates,
            name=self.macllm_name,
            description=self.macllm_description,
            planning_interval=planning_interval,
            managed_agents=managed_agents,
            verbosity_level=LogLevel.ERROR,
            step_callbacks={
                PlanningStep: step_callback,
                ActionStep: step_callback,
                TaskStep: step_callback,
            },
            **kwargs,
        )
