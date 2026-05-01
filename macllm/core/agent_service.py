from __future__ import annotations

from typing import TYPE_CHECKING

from smolagents import PlanningStep, ActionStep, TaskStep

if TYPE_CHECKING:
    from macllm.core.chat_history import Conversation


def extract_plan(text: str) -> str:
    """Extract numbered plan steps from text using ### Plan: ... <end_plan> markers."""
    import re
    lines = text.split('\n')
    collecting = False
    plan_lines: list[str] = []
    for line in lines:
        if re.match(r'^###\s+Plan\s*:', line):
            collecting = True
            continue
        if collecting:
            if '<end_plan>' in line:
                break
            stripped = line.strip()
            if stripped and stripped.strip('`') != '':
                plan_lines.append(line)
    return '\n'.join(plan_lines)


def extract_status(text: str) -> str | None:
    """Extract status summary text using ### Status: ... <end_status> markers."""
    import re
    lines = text.split('\n')
    collecting = False
    status_lines: list[str] = []
    for line in lines:
        if re.match(r'^###\s+Status\s*:', line):
            collecting = True
            continue
        if collecting:
            if '<end_status>' in line:
                break
            stripped = line.strip()
            if stripped and stripped.strip('`') != '':
                status_lines.append(line)
    if not status_lines:
        return None
    return '\n'.join(status_lines)


def create_step_callback(conversation: Conversation | None = None):
    """Create a callback for smolagents step events.

    Increments token usage directly on *conversation.usage* and
    triggers a UI repaint so the top bar stays current.
    """

    def on_step(step, agent):
        should_notify = False
        if isinstance(step, PlanningStep) and conversation is not None:
            raw = getattr(getattr(step, "model_output_message", None), "content", "")
            if not isinstance(raw, str):
                raw = str(raw or "")
            conversation.plan_text = extract_plan(raw) or None
            conversation.plan_status = extract_status(raw)
            should_notify = True

        if isinstance(step, (PlanningStep, ActionStep)):
            if step.token_usage and conversation is not None:
                conversation.usage.input_tokens += step.token_usage.input_tokens
                conversation.usage.output_tokens += step.token_usage.output_tokens
                should_notify = True

        if should_notify and conversation is not None:
            conversation._notify_ui()

    return on_step


def create_agent(agent_cls=None, speed="normal", conversation=None):
    """Thin factory for creating agent instances."""
    if agent_cls is None:
        from macllm.agents import get_default_agent_class
        agent_cls = get_default_agent_class()
    return agent_cls(speed=speed, conversation=conversation)
