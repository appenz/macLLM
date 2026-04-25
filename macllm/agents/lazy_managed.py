"""Lazy-managed subagents: defer MacLLMAgent construction until first delegation.

Eager construction ran ``preload_skill`` and full ``__init__`` for every managed
subagent whenever the parent agent was created, even if the model never called
that subagent.  This wrapper keeps the same ``name`` / ``description`` / calling
convention smolagents expects, but only builds the real agent on first ``__call__``.
"""

from __future__ import annotations

from typing import Any, Callable


class LazyManagedMacLLMAgent:
    __slots__ = (
        "_agent_cls",
        "_speed",
        "_token_callback",
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
        token_callback: Callable[..., Any] | None,
        **kwargs: Any,
    ) -> None:
        from macllm.agents import get_agent_class

        self._agent_cls = get_agent_class(macllm_name)
        self.name = self._agent_cls.macllm_name
        self.description = self._agent_cls.macllm_description
        self._speed = speed
        self._token_callback = token_callback
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
        from macllm.macllm import MacLLM

        self._impl = self._agent_cls(
            speed=self._speed,
            token_callback=self._token_callback,
            managed_agents=[],
            max_steps=5,
            **self._kwargs,
        )
        self._impl.interrupt_switch = self._interrupt_switch
        if MacLLM._instance is not None:
            MacLLM._instance.debug_log(
                f"[agent] managed subagent {self.name!r} materialized (lazy)"
            )
        return self._impl

    def __call__(self, task: str, **kwargs):
        return self._materialize().__call__(task, **kwargs)
