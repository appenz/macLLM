from __future__ import annotations

from typing import TYPE_CHECKING

from smolagents import PlanningStep, ActionStep, TaskStep
from macllm.core.conversationlog import append_plan, current_activity_trace

if TYPE_CHECKING:
    from macllm.core.chat_history import Conversation


def extract_plan(text: str) -> str:
    """Extract plan steps between ``### Plan:`` and ``### Status:`` or ``<end_plan>``."""
    import re
    lines = text.split('\n')
    collecting = False
    plan_lines: list[str] = []
    for line in lines:
        if re.match(r'^###\s+Plan\s*:', line):
            collecting = True
            continue
        if collecting:
            if '<end_plan>' in line or re.match(r'^###\s+Status\s*:', line):
                break
            stripped = line.strip()
            if stripped and stripped.strip('`') != '':
                plan_lines.append(line)
    return '\n'.join(plan_lines)


def extract_status(text: str) -> str | None:
    """Extract status summary from ``### Status:`` to ``<end_plan>`` / ``<end_status>`` / end."""
    import re
    lines = text.split('\n')
    collecting = False
    status_lines: list[str] = []
    for line in lines:
        if re.match(r'^###\s+Status\s*:', line):
            collecting = True
            continue
        if collecting:
            if '<end_status>' in line or '<end_plan>' in line:
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

    def mark_once(step, attr: str) -> bool:
        if getattr(step, attr, False):
            return False
        try:
            setattr(step, attr, True)
        except Exception:
            pass
        return True

    def on_step(step, agent):
        should_notify = False
        if isinstance(step, PlanningStep) and conversation is not None:
            raw = getattr(getattr(step, "model_output_message", None), "content", "")
            if not isinstance(raw, str):
                raw = str(raw or "")
            append_plan(
                conversation.conversation_log,
                text=extract_plan(raw) or None,
                status=extract_status(raw),
            )
            trace = current_activity_trace(conversation.conversation_log)
            if trace is not None:
                token_usage = None
                if mark_once(step, "_macllm_trace_tokens_recorded"):
                    token_usage = getattr(step, "token_usage", None)
                trace.close_current_model_step(
                    label="Planning",
                    token_usage=token_usage,
                )
            should_notify = True

        if isinstance(step, ActionStep) and conversation is not None:
            is_parent = (agent is conversation.agent)
            step_done = (getattr(step, 'observations', None) is not None
                         or getattr(step, 'error', None) is not None)
            trace = current_activity_trace(conversation.conversation_log)
            if trace is not None:
                label = "Final answer" if getattr(step, "is_final_answer", False) else "Thinking"
                token_usage = None
                if mark_once(step, "_macllm_trace_tokens_recorded"):
                    token_usage = getattr(step, "token_usage", None)
                    if step_done:
                        tool_calls = getattr(step, "tool_calls", None) or []
                        for tc in tool_calls:
                            name = tc.get("name", "") if isinstance(tc, dict) else getattr(tc, "name", "")
                            conversation.record_last_tool_result(
                                name,
                                getattr(step, "observations", None),
                            )
                if step_done:
                    trace.close_current_model_step(
                        label=label,
                        token_usage=token_usage,
                        state="error" if getattr(step, "error", None) else "success",
                    )
                else:
                    trace.update_current_model_step(
                        label=label,
                        token_usage=token_usage,
                    )
            if is_parent and step_done:
                conversation.clear_tool_calls()
                should_notify = True

        if isinstance(step, (PlanningStep, ActionStep)):
            if (
                step.token_usage
                and conversation is not None
                and mark_once(step, "_macllm_usage_recorded")
            ):
                conversation.usage.input_tokens += step.token_usage.input_tokens
                conversation.usage.output_tokens += step.token_usage.output_tokens
                should_notify = True

        if should_notify and conversation is not None:
            conversation._notify_ui()

    return on_step


def create_agent(agent_cls=None, speed="normal", conversation=None, no_tools=False):
    """Thin factory for creating agent instances."""
    if agent_cls is None:
        from macllm.agents import get_default_agent_class
        agent_cls = get_default_agent_class()
    return agent_cls(speed=speed, conversation=conversation, no_tools=no_tools)
