from __future__ import annotations

import copy
from typing import TYPE_CHECKING

import litellm
from smolagents import ToolCallingAgent, LogLevel, PlanningStep, ActionStep, TaskStep

if TYPE_CHECKING:
    from macllm.core.chat_history import Conversation

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
    no_tools_notice = (
        "Answer this WITHOUT using tools or subagents; they are disabled for this request. "
        "Answer using only your own knowledge and the conversation so far."
    )

    def __init__(self, speed: str = "normal",
                 conversation: Conversation | None = None,
                 managed_agents: list | None = None,
                 custom_instructions: str | None = None,
                 prompt_templates: dict | None = None,
                 planning_interval: int = 1,
                 no_tools: bool = False,
                 task_mode: bool = False,
                 managed_mode: bool = False,
                 **kwargs):
        from macllm.core.llm_service import MODELS
        from macllm import tools as tools_module
        from macllm.core.agent_service import create_step_callback
        from macllm.core.skills import SkillsRegistry
        from macllm.core.config import get_runtime_config

        self._task_mode = task_mode
        self._managed_mode = managed_mode
        self._tools_disabled = False
        if conversation is not None:
            self._user_situation = conversation.get_user_situation()
        else:
            from macllm.core.device_context import get_device_context
            self._user_situation = get_device_context()

        model = MODELS.get(speed.lower(), MODELS['normal'])
        if model is None:
            raise ValueError(f"Model for speed '{speed}' is not configured (missing API key)")

        tool_names = list(self.macllm_tools)
        if task_mode:
            tool_names = [n for n in tool_names if n != "ask_user"]
        if not task_mode and not managed_mode:
            try:
                from macllm.macllm import MacLLM
                app = MacLLM._instance
                if app is not None and getattr(app, "ephemeral", False):
                    tool_names = [n for n in tool_names if n != "ask_user"]
            except Exception:
                pass

        tools = [getattr(tools_module, n) for n in tool_names]
        self._interactive_mode = (
            not task_mode
            and not managed_mode
            and "ask_user" in tool_names
        )
        step_callback = create_step_callback(conversation)

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
        has_read_skill = "read_skill" in tool_names
        if skill_names is not None and not has_read_skill:
            tools.append(getattr(tools_module, "read_skill"))
            has_read_skill = True

        if managed_agents is None and self.macllm_managed_agents:
            from macllm.agents.lazy_managed import LazyManagedMacLLMAgent

            managed_agents = [
                LazyManagedMacLLMAgent(
                    name,
                    speed=speed,
                    conversation=conversation,
                )
                for name in self.macllm_managed_agents
            ]

        if no_tools:
            tools = []
            managed_agents = []
            planning_interval = None
            custom_instructions = (
                f"{(custom_instructions or '').rstrip()}\n\n{self.no_tools_notice}".strip()
            )

        skills_catalog = (
            SkillsRegistry.model_catalog_text(names=skill_names)
            if has_read_skill and not no_tools else ""
        )
        self._skills_catalog = skills_catalog

        if prompt_templates is None:
            from macllm.agents.macllm_prompt_templates import MACLLM_AGENT_PROMPT_TEMPLATES

            prompt_templates = MACLLM_AGENT_PROMPT_TEMPLATES
        prompt_templates = copy.deepcopy(prompt_templates)

        from smolagents.agents import populate_template

        planning = prompt_templates["planning"]
        planning_context = planning.pop("context", "")
        if planning_context:
            context = populate_template(
                planning_context,
                variables={
                    "custom_instructions": custom_instructions,
                    "skills_catalog": skills_catalog,
                },
            )
            for key in ("initial_plan", "update_plan_pre_messages"):
                planning[key] = planning[key].replace("{{planning_context}}", context)

        if conversation is not None:
            from macllm.core.abortable_model import AbortableModel
            model = AbortableModel(model, conversation.abort_event, conversation)

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

    def _generate_planning_step(self, task, is_first_step, step):
        self._updating_plan = not is_first_step
        try:
            yield from super()._generate_planning_step(task, is_first_step, step)
        finally:
            self._updating_plan = False

    def write_memory_to_messages(self, summary_mode=False):
        if not (summary_mode and getattr(self, "_updating_plan", False)):
            return super().write_memory_to_messages(summary_mode)

        latest = next(
            (item for item in reversed(self.memory.steps)
             if isinstance(item, PlanningStep)),
            None,
        )
        messages = self.memory.system_prompt.to_messages(summary_mode=True)
        for item in self.memory.steps:
            messages.extend(item.to_messages(summary_mode=item is not latest))
        return messages

    def initialize_system_prompt(self) -> str:
        from smolagents.agents import populate_template

        if self._managed_mode:
            template_name = "subagent_system_prompt"
        elif self._interactive_mode:
            template_name = "supervising_system_prompt"
        else:
            template_name = "task_runner_system_prompt"

        prompt = populate_template(
            self.prompt_templates[template_name],
            variables={
                "tools": self.tools,
                "managed_agents": self.managed_agents,
                "custom_instructions": self.instructions,
                "skills_catalog": self._skills_catalog,
                "user_situation": self._user_situation,
                "task_mode": self._task_mode,
                "managed_mode": self._managed_mode,
                "interactive_mode": self._interactive_mode,
            },
        )
        if self._tools_disabled:
            prompt = f"{prompt.rstrip()}\n\n{self.no_tools_notice}"
        return prompt

    def execute_tool_call(self, tool_name, arguments):
        if self._tools_disabled and tool_name != "final_answer":
            from smolagents.agents import AgentToolExecutionError
            raise AgentToolExecutionError(
                f"Tool '{tool_name}' is disabled for this request.", self.logger
            )
        return super().execute_tool_call(tool_name, arguments)

    @staticmethod
    def _debug(msg: str):
        try:
            from macllm.macllm import MacLLM
            if MacLLM._instance is not None:
                MacLLM._instance.debug_log(msg)
        except Exception:
            pass

    def provide_final_answer(self, task):
        """Override to pass the ``final_answer`` tool to the LLM call.

        Smolagents' default ``provide_final_answer`` sends the agent's memory
        to the model *without* any tools.  Tool-calling models (Gemini in
        particular) see tool-call patterns in the history and try to respond
        with a tool call anyway, which the API rejects as a malformed call
        and returns empty content.  By offering ``final_answer`` as an
        available tool the model can either respond with plain text or call
        the tool -- both paths produce a usable answer.
        """
        from smolagents.models import ChatMessage, MessageRole
        from smolagents.agents import populate_template

        messages = [
            ChatMessage(
                role=MessageRole.SYSTEM,
                content=[{
                    "type": "text",
                    "text": self.prompt_templates["final_answer"]["pre_messages"],
                }],
            )
        ]
        messages += self.write_memory_to_messages()[1:]
        messages.append(
            ChatMessage(
                role=MessageRole.USER,
                content=[{
                    "type": "text",
                    "text": populate_template(
                        self.prompt_templates["final_answer"]["post_messages"],
                        variables={"task": task},
                    ),
                }],
            )
        )
        try:
            chat_message = self.model.generate(
                messages,
                tools_to_call_from=[self.tools["final_answer"]],
            )
        except Exception as e:
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content=f"Error in generating final LLM output: {e}",
            )

        if chat_message.content is None and chat_message.tool_calls:
            for tc in chat_message.tool_calls:
                if tc.function.name == "final_answer":
                    args = tc.function.arguments
                    if isinstance(args, dict):
                        answer = args.get("answer", str(args))
                    else:
                        answer = str(args)
                    chat_message.content = str(answer) if answer is not None else ""
                    break

        return chat_message

    def __call__(self, *args, **kwargs):
        return super().__call__(*args, **kwargs)
