from __future__ import annotations

import re


def extract_update(text: str | None) -> str | None:
    if not text:
        return None
    match = re.search(r"<update>(.*?)</update>", text, re.IGNORECASE | re.DOTALL)
    update = " ".join(match.group(1).split()) if match else ""
    return update or None


def without_update(text: str) -> str:
    return re.sub(
        r"<update>.*?(?:</update>|$)", "", text, flags=re.IGNORECASE | re.DOTALL
    ).strip()


def active_run_entries(log):
    start = next(
        (i + 1 for i in range(len(log) - 1, -1, -1) if log[i].kind == "run_start"),
        0,
    )
    return log[start:]


def active_plan(log):
    return next(
        (
            item.payload
            for item in reversed(active_run_entries(log))
            if item.kind == "plan" and isinstance(item.payload, dict)
        ),
        None,
    )


def project_activity(log, parent_name: str):
    """Return (persistent updates, ephemeral (kind, value)) for the active run."""
    updates, pending, current = [], None, None

    for item in active_run_entries(log):
        payload = item.payload
        if item.kind == "planning_started" and payload == parent_name:
            pending, current = None, ("planning", None)
        elif item.kind == "action_started" and payload == parent_name:
            if pending:
                updates.append(pending)
            pending, current = None, None
        elif item.kind == "step" and isinstance(payload, dict):
            if (
                payload.get("step_type") == "planning"
                and payload.get("agent_name") == parent_name
            ):
                pending = extract_update(payload.get("model_output"))
                current = ("update", pending) if pending else None
            elif (
                payload.get("step_type") == "action"
                and payload.get("agent_name") == parent_name
                and (
                    payload.get("observations") is not None
                    or payload.get("error") is not None
                )
            ):
                current = None
            elif (
                payload.get("step_type") == "task"
                and payload.get("agent_role") == "subagent"
                and payload.get("observations") is None
            ):
                current = ("subagent", payload.get("agent_name") or "managed")
        elif item.kind == "tool_call" and isinstance(payload, dict):
            current = ("tool", payload)

    return updates, current
