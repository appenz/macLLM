# Agent Status

## Overview

During agent execution, macLLM shows a live status block in the conversation view.

The status system has two goals:

- show the current plan produced by the agent
- show the progress of tool calls and managed-agent delegation

The status model is intentionally simple. It tracks only user-visible execution state, not the
full internal smolagents trace.

## Architecture

`AgentStatusManager` in `macllm/core/agent_status.py` is the central status object.

It stores:

- `plan`: the current extracted plan text
- `tool_calls`: an ordered log of tool and managed-agent activity

Each tool-call entry is represented by `ToolCallEntry`, which captures:

- stable call identity
- display name
- summarized arguments
- running / success / error state
- optional result or error summary
- indentation level for nested managed-agent activity

The manager is owned by `MacLLM` and updated during a single agent run, then reset before the next run.

## Status Sources

Status comes from two different sources.

Planning status comes from the smolagents step callback in `macllm/core/agent_service.py`.
`create_step_callback()` extracts the current plan from `PlanningStep` and forwards it to
`AgentStatusManager.set_plan()`.

Execution status comes from tools and managed agents.

- tools call `start_tool_call()`, `complete_tool_call()`, and `fail_tool_call()` directly
- managed-agent delegation is reported by `MacLLMAgent.__call__()` through `enter_managed_agent()` and `exit_managed_agent()`

This split is a key design decision: plan text comes from agent planning events, but tool progress does not.
Tool progress is owned by the tool implementations themselves.

## Managed-Agent Nesting

Managed-agent delegation is represented as part of the same status stream as normal tool calls.

When a parent agent delegates work:

- the status manager inserts a running entry for the managed agent
- nested tool calls are indented under that managed agent
- the managed-agent entry is marked complete when control returns

This allows one unified status block in the UI instead of separate views for top-level and delegated work.

## Rendering Model

The status manager exposes a text `render()` method, but the conversation UI does not display that raw text directly.

`MainTextHandler._render_agent_status()` in `macllm/ui/main_text.py` reads the structured state and renders:

- a `Plan` section when `plan` is present
- a `Steps` section when `tool_calls` is non-empty
- nested indentation for managed-agent activity
- visual status markers for running, success, and error states

The UI therefore depends on the structured fields of `AgentStatusManager`, not just on the output of `render()`.

## API Surface

The architectural API of `AgentStatusManager` is:

- `set_plan(plan)`
- `enter_managed_agent(name, task)`
- `exit_managed_agent(name)`
- `start_tool_call(id, name, args)`
- `complete_tool_call(id, result="")`
- `fail_tool_call(id, error)`
- `reset()`

All mutating methods notify the UI through the manager's `ui_update_callback`.

## Design Notes

- The status system is global to the active `MacLLM` instance, not per tool or per UI component.
- Instant tools can skip `start_tool_call()` and still appear as successful entries when `complete_tool_call()` is called.
- Error display is intentionally summarized rather than storing full exception traces.
