# Agent Status Display

## Overview

During agent execution, macLLM shows live progress in the conversation view.

The display has two goals:

- show the progress of tool calls and managed-agent delegation
- show pending shell approval requests that need user action

## Data Source

All progress data comes from `agent.memory.steps` on the conversation's agent instance.

smolagents records each step as a dataclass in the step list:

- `PlanningStep`: the agent produced a plan (not currently displayed)
- `ActionStep`: the agent called a tool. Contains `tool_calls` (name, arguments, id), `observations` (tool output), `error` (if failed), and `is_final_answer`
- `TaskStep`: the agent delegated to a managed subagent

The UI renders these directly. There is no intermediate status manager object.

### Determining tool state from ActionStep

- `tool_calls` populated, `observations` is None, `error` is None → tool is currently running
- `observations` is not None → tool completed successfully
- `error` is not None → tool failed

### Pending approval

Shell approval state lives on `Conversation.pending_approval` (a transient `PendingApproval` dataclass, not persisted). When a tool sets this field and calls `request_update()`, the UI renders the approval widget as the last item in the conversation view. Once the user decides, the field is cleared.

## Rendering

`MainTextHandler` in `macllm/ui/main_text.py` reads the conversation's step list and pending approval to render:

- a `Steps` section with status markers (running, success, error) for each tool call
- nested indentation for managed-agent delegation (from `TaskStep` entries)
- an inline approval prompt when `conversation.pending_approval` is set

## Previous Architecture

The previous `AgentStatusManager` class has been removed. It used to track plan text, tool call entries, and pending approvals as a separate object owned by `MacLLM`. Tools reported their own progress by calling `start_tool_call()`, `complete_tool_call()`, and `fail_tool_call()`.

This was replaced by rendering directly from `agent.memory.steps`, which smolagents already maintains as part of its execution loop. This eliminates a redundant layer and makes the conversation the sole data source for the UI. See `specs/parallel_tabs.md` for context.
