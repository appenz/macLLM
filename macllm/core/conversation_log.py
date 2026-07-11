from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from typing import Any

RUNTIME_FACT_KINDS = {"run_start", "run_end", "step"}
ACTIVITY_MARKER_KINDS = {"planning_started", "action_started"}


@dataclass
class ConversationLogEntry:
    kind: str
    timestamp: float
    payload: Any
    tokens: int | None = None


class ConversationLog(list[ConversationLogEntry]):
    """Append-only chronological record of conversation facts."""


def entry(kind: str, payload: Any, *, tokens: int | None = None) -> ConversationLogEntry:
    """Create a log entry, preserving payload state when practical."""
    return ConversationLogEntry(
        kind=kind,
        timestamp=time.time(),
        payload=_preserve_payload(payload),
        tokens=tokens,
    )


def message(role: str, content: str) -> ConversationLogEntry:
    return entry("message", {"role": role, "content": content})


def append_run_start(log: list[ConversationLogEntry], payload: dict) -> None:
    log.append(entry("run_start", _stable_payload(payload)))


def append_run_end(log: list[ConversationLogEntry], payload: dict) -> None:
    log.append(entry("run_end", _stable_payload(payload)))


def append_step(log: list[ConversationLogEntry], payload: dict, *, tokens: int | None = None) -> None:
    log.append(entry("step", _stable_payload(payload), tokens=tokens))


def append_activity_marker(
    log: list[ConversationLogEntry], kind: str, agent_name: str
) -> None:
    if kind not in ACTIVITY_MARKER_KINDS:
        raise ValueError(f"Unknown activity marker: {kind}")
    log.append(entry(kind, agent_name))


def clear_activity_markers(log: list[ConversationLogEntry]) -> None:
    log[:] = [item for item in log if item.kind not in ACTIVITY_MARKER_KINDS]


def append_agent_step(
    log: list[ConversationLogEntry],
    step: Any,
    *,
    step_type: str,
    agent_name: str,
    agent_role: str,
) -> None:
    """Append a primitive projection of an accessible agent step."""
    payload = _agent_step_payload(
        step,
        step_type=step_type,
        agent_name=agent_name,
        agent_role=agent_role,
    )
    tokens = payload.get("token_usage") or {}
    log.append(entry("step", payload, tokens=tokens.get("total_tokens")))


def token_usage_totals(log: list[ConversationLogEntry]) -> tuple[int, int]:
    """Return cumulative input/output tokens recorded in step facts."""
    input_tokens = 0
    output_tokens = 0
    for item in log:
        payload = getattr(item, "payload", None)
        if not isinstance(payload, dict):
            continue
        usage = payload.get("token_usage")
        if not isinstance(usage, dict):
            continue
        input_tokens += int(usage.get("input_tokens", 0) or 0)
        output_tokens += int(usage.get("output_tokens", 0) or 0)
    return input_tokens, output_tokens


def add_tool_call(log: list[ConversationLogEntry], tool_name: str, message_text: str) -> None:
    log.append(ConversationLogEntry(
        kind="tool_call",
        timestamp=time.time(),
        payload={"tool": tool_name, "message": message_text},
    ))


def update_last_tool_message(log: list[ConversationLogEntry], message_text: str) -> None:
    item = _last_tool_call_entry(log)
    if item is None or not isinstance(item.payload, dict):
        return
    item.payload["message"] = message_text


def complete_last_tool_call(log: list[ConversationLogEntry], *, failed: bool = False) -> None:
    """Compatibility hook for tools; step state is recorded by smolagents."""


def record_last_tool_result(log: list[ConversationLogEntry], tool_name: str, result) -> None:
    """Compatibility hook; result text lives on the corresponding ActionStep."""


def pop_last_tool_call(log: list[ConversationLogEntry]) -> None:
    for index in range(len(log) - 1, -1, -1):
        item = log[index]
        if item.kind != "tool_call":
            continue
        del log[index]
        return


def tool_calls(log: list[ConversationLogEntry]) -> list[dict]:
    calls: list[dict] = []
    for item in log:
        if item.kind == "tool_call" and isinstance(item.payload, dict):
            calls.append(item.payload)
    return calls


def clear_tool_calls(log: list[ConversationLogEntry]) -> None:
    log[:] = [item for item in log if item.kind != "tool_call"]


def _last_tool_call_entry(log: list[ConversationLogEntry]) -> ConversationLogEntry | None:
    for item in reversed(log):
        if item.kind == "tool_call":
            return item
    return None


def append_plan(log: list[ConversationLogEntry], *, text: str | None = None, status: str | None = None) -> None:
    prev = latest_plan(log)
    log.append(entry("plan", {
        "text": text if text is not None else (prev or {}).get("text"),
        "status": status if status is not None else (prev or {}).get("status"),
    }))


def latest_plan(log: list[ConversationLogEntry]) -> dict | None:
    for item in reversed(log):
        if item.kind == "plan" and isinstance(item.payload, dict):
            return item.payload
    return None


def persistable_log(log: list[ConversationLogEntry]) -> ConversationLog:
    stable = ConversationLog()
    for item in log:
        if item.kind in {"message", "plan", *RUNTIME_FACT_KINDS}:
            stable.append(ConversationLogEntry(
                kind=item.kind,
                timestamp=item.timestamp,
                payload=_preserve_payload(item.payload),
                tokens=item.tokens,
            ))
    return stable


def messages_from_log(log: list[ConversationLogEntry]) -> list[dict]:
    messages: list[dict] = []
    for item in log:
        if item.kind != "message":
            continue
        payload = item.payload
        if not isinstance(payload, dict):
            continue
        role = payload.get("role")
        content = payload.get("content")
        if role in {"user", "assistant", "system"} and isinstance(content, str):
            messages.append({"role": role, "content": content})
    return messages


def log_from_messages(messages: list[dict]) -> ConversationLog:
    log = ConversationLog()
    for msg in messages:
        if not isinstance(msg, dict):
            continue
        role = msg.get("role")
        content = msg.get("content")
        if role in {"user", "assistant", "system"} and isinstance(content, str):
            log.append(message(role, content))
    return log


def _preserve_payload(payload: Any) -> Any:
    try:
        return copy.deepcopy(payload)
    except Exception:
        try:
            return copy.copy(payload)
        except Exception:
            return payload


def _stable_payload(payload: Any) -> Any:
    """Return a pickle-friendly primitive projection of runtime facts."""
    return _stable_value(payload)


def _agent_step_payload(
    step: Any,
    *,
    step_type: str,
    agent_name: str,
    agent_role: str,
) -> dict:
    payload = {
        "agent_name": str(agent_name or "agent"),
        "agent_role": agent_role,
        "step_type": step_type,
        "step_number": getattr(step, "step_number", None),
        "token_usage": _token_usage_payload(step),
        "timing": _timing_payload(step),
    }

    if step_type == "planning":
        payload.update({
            "plan": getattr(step, "plan", None),
            "model_output": _message_content(getattr(step, "model_output_message", None)),
        })
    elif step_type == "action":
        payload.update({
            "model_output": _message_content(getattr(step, "model_output_message", None)),
            "tool_calls": [
                _tool_call_payload(tc)
                for tc in (getattr(step, "tool_calls", None) or [])
            ],
            "observations": getattr(step, "observations", None),
            "error": str(getattr(step, "error", "")) if getattr(step, "error", None) else None,
            "is_final_answer": bool(getattr(step, "is_final_answer", False)),
        })
    elif step_type == "task":
        payload.update({
            "task": getattr(step, "task", None),
            "observations": getattr(step, "observations", None),
            "error": str(getattr(step, "error", "")) if getattr(step, "error", None) else None,
        })
    return _stable_payload(payload)


def _token_usage_payload(step: Any) -> dict | None:
    usage = getattr(step, "token_usage", None)
    if not usage:
        return None
    input_tokens = int(getattr(usage, "input_tokens", 0) or 0)
    output_tokens = int(getattr(usage, "output_tokens", 0) or 0)
    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
    }


def _timing_payload(step: Any) -> dict | None:
    timing = getattr(step, "timing", None)
    if timing is None:
        return None
    payload = {}
    for name in ("start_time", "end_time", "duration"):
        value = getattr(timing, name, None)
        if value is not None:
            try:
                payload[name] = float(value)
            except Exception:
                payload[name] = str(value)
    if "duration" not in payload and {"start_time", "end_time"} <= payload.keys():
        payload["duration"] = payload["end_time"] - payload["start_time"]
    return payload or None


def _message_content(message: Any) -> str | None:
    if message is None:
        return None
    content = getattr(message, "content", None)
    if content is None:
        return None
    return content if isinstance(content, str) else str(content)


def _tool_call_payload(tool_call: Any) -> dict:
    if isinstance(tool_call, dict):
        return {
            "name": tool_call.get("name"),
            "arguments": tool_call.get("arguments", {}),
            "id": tool_call.get("id"),
        }
    return {
        "name": getattr(tool_call, "name", None),
        "arguments": getattr(tool_call, "arguments", {}),
        "id": getattr(tool_call, "id", None),
    }


def _stable_value(value: Any, depth: int = 0) -> Any:
    if depth > 8:
        return repr(value)
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, dict):
        return {
            str(k): _stable_value(v, depth + 1)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_stable_value(v, depth + 1) for v in value]
    try:
        return copy.deepcopy(value)
    except Exception:
        return repr(value)
