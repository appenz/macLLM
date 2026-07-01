from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from typing import Any


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
        if item.kind in {"message", "plan"}:
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
