# Tools

## Overview

Tools are the callable operations exposed to agents.

They are implemented under `macllm/tools/`, exported from `macllm/tools/__init__.py`, and referenced by agents symbolically through tool-name strings.

## Design

The main design choice is that tools are the operational boundary of the agent system.

- agents decide what work to do
- tools perform the concrete work
- tool names are the stable contract between agent configuration and implementation

Tools return human-readable strings and report progress directly to `AgentStatusManager`.

## Tool Families

The current tool set is organized by domain:

- general utilities such as time and web search
- file tools for local notes and indexed files (including `folder_create` / `folder_delete` for subfolders under indexed roots; deletes are backed up like note deletes)
- calendar tools for scheduling and event lookup
- Things tools for task management
- skill tools such as `read_skill`
- memory tools for long-term agent recall

Files and calendar have deeper subsystem docs because they combine tools with additional indexing or agent structure. The rest of the tool layer is intentionally lightweight.

# Tools (agent API)

Tools are smolagents `@tool` callables exported from macllm/tools/ and referenced by name on each `MacLLMAgent` (`macllm_tools`).

## Resolution

`MacLLMAgent.__init__` maps each string in `macllm_tools` to an attribute on the macllm.tools package. Unknown names fail at construction.

## Families (structural)

- General — e.g. time, web search.
- Files — Index-backed search/read and filesystem mutators scoped to agent rules (see [files.md](files.md)).
- Calendar — EventKit-backed read/write helpers (see [calendar.md](calendar.md)).
- Skills — `read_skill` loads markdown skill bodies for the model (see [skills.md](skills.md)).
- Memory — `remember` appends to a daily markdown file for long-term recall.

## Side effects and status

Tools may report progress via `AgentStatusManager` (`start` / `complete` / `fail`). Long-running tools typically pair start and end; fast tools may complete without a prior start.

## Boundaries

Tools are not tag plugins. User @ expansion happens before the agent; tools operate on the expanded task and return string observations to the agent loop.

Current export surface: see macllm/tools/__all__ for the authoritative name list.
