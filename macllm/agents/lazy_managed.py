"""Lazy-managed subagents: defer MacLLMAgent construction until first delegation.

Eager construction ran ``preload_skill`` and full ``__init__`` for every managed
subagent whenever the parent agent was created, even if the model never called
that subagent.  This wrapper keeps the same ``name`` / ``description`` / calling
convention smolagents expects, but only builds the real agent on first ``__call__``.
"""

from __future__ import annotations

from typing import Any


class LazyManagedMacLLMAgent:
    __slots__ = (
        "_agent_cls",
        "_speed",
        "_conversation",
        "_kwargs",
        "_impl",
        "_interrupt_switch",
        "name",
        "description",
        "inputs",
        "output_type",
    )

    def __init__(
        self,
        macllm_name: str,
        *,
        speed: str,
        conversation: Any | None = None,
        **kwargs: Any,
    ) -> None:
        from macllm.agents import get_agent_class

        self._agent_cls = get_agent_class(macllm_name)
        self.name = self._agent_cls.macllm_name
        self.description = self._agent_cls.macllm_description
        self._speed = speed
        self._conversation = conversation
        self._kwargs = kwargs
        self._impl = None
        self._interrupt_switch = False
        self.inputs = {}
        self.output_type = "string"

    @property
    def interrupt_switch(self) -> bool:
        return self._interrupt_switch

    @interrupt_switch.setter
    def interrupt_switch(self, value: bool) -> None:
        self._interrupt_switch = bool(value)
        if self._impl is not None:
            self._impl.interrupt_switch = self._interrupt_switch

    def _materialize(self):
        if self._impl is not None:
            return self._impl

        self._impl = self._agent_cls(
            speed=self._speed,
            conversation=self._conversation,
            managed_agents=[],
            max_steps=5,
            managed_mode=True,
            **self._kwargs,
        )
        self._impl.planning_interval = None
        self._impl.interrupt_switch = self._interrupt_switch
        return self._impl

    def __call__(self, task: str, **kwargs):
        if self._conversation is not None:
            try:
                from macllm.core.conversation_log import append_step

                append_step(
                    self._conversation.conversation_log,
                    {
                        "agent_name": self.name,
                        "agent_role": "subagent",
                        "step_type": "task",
                        "step_number": None,
                        "task": task,
                        "observations": None,
                        "error": None,
                    },
                )
                self._conversation._notify_ui()
            except Exception:
                pass
        agent = self._materialize()
        if self._conversation is None:
            return agent.__call__(task, **kwargs)
        self._conversation.current_agent = agent
        try:
            return agent.__call__(task, **kwargs)
        finally:
            self._conversation.current_agent = self._conversation.agent
