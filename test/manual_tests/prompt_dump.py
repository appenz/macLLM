#!/usr/bin/env python3
"""Manual prompt dump for macLLM agents.

Run with:
    make test-prompts

This does not call an external LLM. It installs a capture model into the same
MODELS map used by agent construction, then lets smolagents build the real
model input messages for a short dry run.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

from smolagents.agents import populate_template
from smolagents.models import ChatMessage, LiteLLMModel, MessageRole

from macllm.agents import get_agent_class
from macllm.agents.base import MacLLMAgent
from macllm.core import llm_service


AGENT_NAMES = ("default", "smolagent", "notes", "calendar", "things", "email")
SUBAGENT_NAMES = ("notes", "calendar", "things", "email")
DEFAULT_TASK = (
    "The user wants help filing a note but the destination folder is ambiguous."
)


class StopAfterCapture(RuntimeError):
    """Raised by the capture model after recording the target model call."""


class CaptureModel:
    """Tiny smolagents-compatible model that records generate() inputs."""

    model_id = "manual-prompt-capture"
    api_key = None
    api_base = None

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def generate(self, messages, **kwargs):  # noqa: ANN001 - matches smolagents
        self.calls.append({"messages": list(messages), "kwargs": dict(kwargs)})

        # Let planned agents get past the initial planning call so we can also
        # capture the first action-step prompt, where tools are available.
        if kwargs.get("stop_sequences") == ["<end_plan>"]:
            return ChatMessage(
                role=MessageRole.ASSISTANT,
                content="### Plan:\n[ ] Inspect the prompt context\n<end_plan>",
            )

        raise StopAfterCapture("captured first non-planning model call")

    def parse_tool_calls(self, chat_message):  # noqa: ANN001 - smolagents API
        return chat_message


@contextmanager
def capture_models():
    old_models = dict(llm_service.MODELS)
    model = CaptureModel()
    llm_service.MODELS.update({"fast": model, "normal": model, "slow": model})
    try:
        yield model
    finally:
        llm_service.MODELS.clear()
        llm_service.MODELS.update(old_models)


def _text_part(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(parts)
    return str(content)


def _role_name(role: Any) -> str:
    return getattr(role, "value", str(role))


def _tool_names(tools: Any) -> list[str]:
    if tools is None:
        return []
    return [
        getattr(tool, "name", repr(tool))
        for tool in tools
    ]


def _print_message_call(call: dict[str, Any], *, heading: str) -> None:
    print(f"\n--- {heading} ---")
    kwargs = call["kwargs"]
    if kwargs:
        print("generate kwargs:")
        for key, value in kwargs.items():
            if key == "tools_to_call_from":
                print(f"  {key}: {_tool_names(value)}")
            else:
                print(f"  {key}: {value!r}")
    for index, message in enumerate(call["messages"], start=1):
        print(f"\n[{index}] role={_role_name(message.role)}")
        print(_text_part(message.content))

    if os.environ.get("PROMPT_DUMP_LITELLM", "").lower() in {"1", "true", "yes"}:
        _print_litellm_payload(call)


def _print_litellm_payload(call: dict[str, Any]) -> None:
    """Show the payload LiteLLMModel would pass to litellm.completion()."""
    kwargs = call["kwargs"]
    model = LiteLLMModel(
        model_id="openai/manual-prompt-capture",
        api_key="dummy",
        api_base="https://example.invalid/v1",
    )
    payload = model._prepare_completion_kwargs(
        messages=call["messages"],
        stop_sequences=kwargs.get("stop_sequences"),
        tools_to_call_from=kwargs.get("tools_to_call_from"),
        model=model.model_id,
        api_key=model.api_key,
        api_base=model.api_base,
        convert_images_to_image_urls=True,
        custom_role_conversions=model.custom_role_conversions,
    )

    print("\nLiteLLM completion kwargs preview:")
    for key, value in payload.items():
        if key == "api_key":
            print("  api_key: <redacted>")
        else:
            print(f"  {key}: {value!r}")


def _make_agent(
    agent_name: str,
    *,
    task_mode: bool = False,
    managed_mode: bool | None = None,
) -> MacLLMAgent:
    cls = get_agent_class(agent_name)
    if managed_mode is None:
        managed_mode = agent_name in SUBAGENT_NAMES
    return cls(speed="normal", task_mode=task_mode, managed_mode=managed_mode)


def _dump_agent_system_prompt(agent_name: str, *, task_mode: bool = False) -> None:
    agent = _make_agent(agent_name, task_mode=task_mode)
    if task_mode:
        mode = "task runner"
    elif agent_name in SUBAGENT_NAMES:
        mode = "managed"
    else:
        mode = "normal"
    print(f"\n\n===== SYSTEM PROMPT: {agent_name} ({mode}) =====")
    print(agent.system_prompt)


def _dump_first_model_inputs(agent_name: str, *, task_mode: bool = False) -> None:
    with capture_models() as model:
        agent = _make_agent(agent_name, task_mode=task_mode)
        try:
            agent.run(DEFAULT_TASK, max_steps=1, reset=True)
        except Exception:
            pass

        print(f"\n\n===== SMOLAGENTS MODEL INPUTS: {agent_name} =====")
        if not model.calls:
            print("No model calls captured.")
            return
        for index, call in enumerate(model.calls, start=1):
            _print_message_call(call, heading=f"model call {index}")


def _dump_managed_task_wrapper(subagent_name: str) -> None:
    manager = _make_agent("default")
    template = manager.prompt_templates["managed_agent"]["task"]
    wrapped = populate_template(
        template,
        variables={"name": subagent_name, "task": DEFAULT_TASK},
    )
    print(f"\n\n===== MANAGED TASK WRAPPER: {subagent_name} =====")
    print(wrapped)


def dump_prompts() -> None:
    print(f"PROMPT_DUMP_TASK={DEFAULT_TASK!r}")
    print("Note: model input capture uses a fake model, but the smolagents run path is real.")
    print("Set PROMPT_DUMP_LITELLM=1 to also show LiteLLM completion kwargs.")

    for agent_name in AGENT_NAMES:
        _dump_agent_system_prompt(agent_name)

    _dump_agent_system_prompt("default", task_mode=True)

    for subagent_name in SUBAGENT_NAMES:
        _dump_managed_task_wrapper(subagent_name)

    capture_name = os.environ.get("PROMPT_DUMP_CAPTURE_AGENT", "default")
    _dump_first_model_inputs(capture_name)


def test_dump_prompts():
    dump_prompts()

