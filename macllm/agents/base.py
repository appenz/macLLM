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
    - ``prompt_templates``    -- full template dict; if omitted (``None``), uses
      :data:`macllm.agents.macllm_prompt_templates.MACLLM_AGENT_PROMPT_TEMPLATES`
      (never smolagents' bundled YAML).
    - ``planning_interval``   -- how often the planning step runs (``None`` disables)

    Subclasses that want no planning pass ``planning_interval=None`` explicitly.
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
        from macllm.core.config import get_runtime_config

        reset_search_counter()

        model = MODELS.get(speed.lower(), MODELS['normal'])
        if model is None:
            raise ValueError(f"Model for speed '{speed}' is not configured (missing API key)")

        tools = [getattr(tools_module, n) for n in self.macllm_tools]
        step_callback = create_step_callback(token_callback)

        cfg = get_runtime_config()
        agent_cfg = cfg.agents.get(self.macllm_name)

        if agent_cfg and agent_cfg.instructions:
            custom_instructions = agent_cfg.instructions

        if agent_cfg and agent_cfg.preload_skill:
            SkillsRegistry.ensure_loaded()
            preload = SkillsRegistry.get(agent_cfg.preload_skill)
            if preload and preload.body:
                custom_instructions = (
                    f"{(custom_instructions or '').rstrip()}\n\n{preload.body.strip()}"
                )
                self._debug(f"[agent:{self.macllm_name}] preloaded skill '{preload.name}'")
            else:
                self._debug(f"[agent:{self.macllm_name}] preload_skill '{agent_cfg.preload_skill}' not found")

        skill_names = agent_cfg.skills if agent_cfg and agent_cfg.skills else None
        has_read_skill = "read_skill" in self.macllm_tools
        if skill_names is not None and not has_read_skill:
            tools.append(getattr(tools_module, "read_skill"))
            has_read_skill = True

        if custom_instructions and has_read_skill:
            skills_catalog = SkillsRegistry.model_catalog_text(names=skill_names)
            custom_instructions = (
                f"{custom_instructions.rstrip()}\n\n"
                "Skill discovery:\n"
                f"{skills_catalog}\n"
                "To retrieve a skill definition, call read_skill with the skill name.\n"
            )

        if managed_agents is None and self.macllm_managed_agents:
            from macllm.agents.lazy_managed import LazyManagedMacLLMAgent

            managed_agents = [
                LazyManagedMacLLMAgent(
                    name,
                    speed=speed,
                    token_callback=token_callback,
                )
                for name in self.macllm_managed_agents
            ]

        if prompt_templates is None:
            from macllm.agents.macllm_prompt_templates import MACLLM_AGENT_PROMPT_TEMPLATES

            prompt_templates = MACLLM_AGENT_PROMPT_TEMPLATES

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

    @staticmethod
    def _debug(msg: str):
        try:
            from macllm.macllm import MacLLM
            if MacLLM._instance is not None:
                MacLLM._instance.debug_log(msg)
        except Exception:
            pass

    def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
