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
    macllm_managed_agents: list[str] = []

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
        from macllm.core.skills import SkillsRegistry

        reset_search_counter()

        model = MODELS.get(speed.lower(), MODELS['normal'])
        if model is None:
            raise ValueError(f"Model for speed '{speed}' is not configured (missing API key)")

        tools = [getattr(tools_module, n) for n in self.macllm_tools]
        step_callback = create_step_callback(token_callback)

        if custom_instructions and "read_skill" in self.macllm_tools:
            skills_catalog = SkillsRegistry.model_catalog_text()
            custom_instructions = (
                f"{custom_instructions.rstrip()}\n\n"
                "Skill discovery:\n"
                f"{skills_catalog}\n"
                "To retrieve a skill definition, call read_skill with the skill name.\n"
            )

        if managed_agents is None and self.macllm_managed_agents:
            from macllm.agents import get_agent_class
            managed_agents = [
                get_agent_class(name)(speed=speed)
                for name in self.macllm_managed_agents
            ]

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

    def __call__(self, *args, **kwargs):
        """Wrap managed-agent invocation to signal the status manager."""
        from macllm.macllm import MacLLM
        task = args[0] if args else kwargs.get("task", "")
        try:
            MacLLM.get_status_manager().enter_managed_agent(self.macllm_name, task)
        except Exception:
            pass
        try:
            return super().__call__(*args, **kwargs)
        finally:
            try:
                MacLLM.get_status_manager().exit_managed_agent(self.macllm_name)
            except Exception:
                pass
