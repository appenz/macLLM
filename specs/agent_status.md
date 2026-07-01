# Agent Status Display

## Overview

During agent execution, macLLM shows live progress in the conversation view.

The display has three goals:

- show supervising-agent planning progress as a checklist and status summary
- show the progress of tool calls and managed-agent delegation
- show pending shell approval requests that need user action

## Data Sources

Progress data comes from two conversation-owned sources:

- `agent.memory.steps` on the conversation's agent instance
- transient `tool_call` entries in `Conversation.conversation_log` while `@macllm_tool` wrappers are actively executing

smolagents records each step as a dataclass in the step list:

- `PlanningStep`: the agent produced or updated a plan
- `ActionStep`: the agent called a tool. Contains `tool_calls` (name, arguments, id), `observations` (tool output), `error` (if failed), and `is_final_answer`
- `TaskStep`: the agent delegated to a managed subagent

`PlanningStep` output is parsed from `step.model_output_message.content` and appended to `Conversation.conversation_log` as a `plan` entry:

- `text`: extracted text between `### Plan:` and `### Status:` (or `<end_plan>`)
- `status`: extracted text after `### Status:` until `<end_plan>` or end of output (optional)

The UI reads the latest plan through `latest_plan()` in `macllm/core/conversation_log.py`, completed/planned tool and delegation data from `agent.memory.steps`, and live in-tool status text from `conversation_log` `tool_call` entries. There is no intermediate status manager or activity-tree object.

### Determining tool state from ActionStep

- `tool_calls` populated, `observations` is None, `error` is None → tool is currently running
- `observations` is not None → tool completed successfully
- `error` is not None → tool failed

### Pending approval

Shell approval state lives on `Conversation.pending_approval` (a transient `PendingApproval` dataclass from `macllm/core/user_interaction.py`, not persisted). When a tool sets this field and requests a repaint, the UI renders the approval widget as the last item in the conversation view. Once the user decides, the field is cleared.

## Rendering

`MainTextHandler` in `macllm/ui/main_text.py` reads the conversation's step list, latest conversation-log plan, transient live tool-call entries, and pending approval to render:

- a **"Plan"** section when the latest conversation-log plan has text (checkbox-style lines from planning output)
- a **"Status"** summary under the plan when the latest conversation-log plan has status text
- a **"Steps"** section with status markers (running, success, error) once tool calls or managed-agent task steps exist
- **"Thinking..."** when the agent is running and neither plan text nor tool calls are available yet
- managed-agent delegation rows from `TaskStep` entries
- an inline approval prompt when `conversation.pending_approval` is set

### Per-tool display formatting

`MainTextHandler._TOOL_DISPLAY` is a UI-local dict mapping tool names to display
formatter lambdas `(args_dict) -> str`. When a tool name has an entry in this dict,
the renderer uses its formatter instead of the generic `name(key=value, ...)` display.
`run_command` is handled separately (monospaced font for the command text).

The detailed debug window is a separate passive renderer. It reads compact chronological runtime facts from `Conversation.conversation_log`, including run start/end facts and accessible step projections recorded by the same step callback for supervisor and managed subagents. The live status view remains intentionally compact.

This keeps the renderer passive — it only reads step data from the conversation and
applies its own presentation rules. No imports from `macllm.tools`.

## Previous Architecture

The previous `AgentStatusManager` class has been removed. It used to track plan text, tool call entries, and pending approvals as a separate object owned by `MacLLM`. Tools reported their own progress by calling `start_tool_call()`, `complete_tool_call()`, and `fail_tool_call()`.

This was replaced by rendering directly from `agent.memory.steps` and `conversation_log`, which smolagents and the conversation runtime already maintain as part of execution. This eliminates redundant layers and makes the conversation the sole data source for the UI. Transient `@macllm_tool` status lines also read from `conversation_log` tool-call entries (see `specs/tools.md`).

The later `ActivityTrace` activity tree was also removed for the same reason: it duplicated step/log state as a transient object inside the conversation log. Live status should remain a direct projection of the conversation log plus smolagents memory.
