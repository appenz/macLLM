# Agent Status Display

## Overview

During agent execution, macLLM shows live progress in the conversation view.

The display has three goals:

- show supervising-agent planning progress as a checklist and status summary
- show the progress of tool calls and managed-agent delegation
- show pending shell approval requests that need user action

## Data Source

All progress data comes from `agent.memory.steps` on the conversation's agent instance.

smolagents records each step as a dataclass in the step list:

- `PlanningStep`: the agent produced or updated a plan
- `ActionStep`: the agent called a tool. Contains `tool_calls` (name, arguments, id), `observations` (tool output), `error` (if failed), and `is_final_answer`
- `TaskStep`: the agent delegated to a managed subagent

`PlanningStep` output is parsed from `step.model_output_message.content` and stored on the conversation as transient text fields:

- `Conversation.plan_text`: extracted text between `### Plan:` and `<end_plan>`
- `Conversation.plan_status`: extracted text between `### Status:` and `<end_status>` (optional)

The UI then renders these conversation fields, plus tool/activity data from `agent.memory.steps`. There is no intermediate status manager object.

### Determining tool state from ActionStep

- `tool_calls` populated, `observations` is None, `error` is None → tool is currently running
- `observations` is not None → tool completed successfully
- `error` is not None → tool failed

### Pending approval

Shell approval state lives on `Conversation.pending_approval` (a transient `PendingApproval` dataclass, not persisted). When a tool sets this field and calls `request_update()`, the UI renders the approval widget as the last item in the conversation view. Once the user decides, the field is cleared.

## Rendering

`MainTextHandler` in `macllm/ui/main_text.py` reads the conversation's step list, plan fields, and pending approval to render:

- a **"Plan"** section when `conversation.plan_text` is present (checkbox-style lines from planning output)
- a **"Status"** summary under the plan when `conversation.plan_status` is present
- a **"Steps"** section with status markers (running, success, error) once tool calls exist
- **"Thinking..."** when the agent is running and neither plan text nor tool calls are available yet
- nested indentation for managed-agent delegation (from `TaskStep` entries)
- an inline approval prompt when `conversation.pending_approval` is set

### Per-tool display formatting

`MainTextHandler._TOOL_DISPLAY` is a UI-local dict mapping tool names to display
formatter lambdas `(args_dict) -> str`. When a tool name has an entry in this dict,
the renderer uses its formatter instead of the generic `name(key=value, ...)` display.
`run_command` is handled separately (monospaced font for the command text).

This keeps the renderer passive — it only reads step data from the conversation and
applies its own presentation rules. No imports from `macllm.tools`.

## Previous Architecture

The previous `AgentStatusManager` class has been removed. It used to track plan text, tool call entries, and pending approvals as a separate object owned by `MacLLM`. Tools reported their own progress by calling `start_tool_call()`, `complete_tool_call()`, and `fail_tool_call()`.

This was replaced by rendering directly from `agent.memory.steps`, which smolagents already maintains as part of its execution loop. This eliminates a redundant layer and makes the conversation the sole data source for the UI. Transient `@macllm_tool` status lines also read from `conversation.tool_calls` (see `specs/tools.md`).
