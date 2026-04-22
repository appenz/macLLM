# Tools

## Overview

Tools are the callable operations exposed to agents.

They are implemented under `macllm/tools/`, exported from `macllm/tools/__init__.py`, and referenced by agents symbolically through tool-name strings.

## Design

The main design choice is that tools are the operational boundary of the agent system.

- agents decide what work to do
- tools perform the concrete work
- tool names are the stable contract between agent configuration and implementation

Tools return human-readable strings. Tool execution progress is recorded by smolagents in `agent.memory.steps` and rendered by the UI from there. Tools do not report status directly.

## Tool Families

The current tool set is organized by domain:

- general utilities such as time and web search
- note/file tools for local notes under mount-point directories: search, read, create, append, modify, move, delete notes; create/delete subfolders; list and find folders; resolve mount-relative paths to absolute paths (see [file_plugin.md](file_plugin.md))
- calendar tools for scheduling and event lookup
- Things tools for task management
- skill tools such as `read_skill`
- email tools for read-only access to the local Superhuman mailbox via shmail
- memory tools for long-term agent recall

Files and calendar have deeper subsystem docs because they combine tools with additional indexing or agent structure. The rest of the tool layer is intentionally lightweight.

# Tools (agent API)

Tools are smolagents `@tool` callables exported from macllm/tools/ and referenced by name on each `MacLLMAgent` (`macllm_tools`).

## Resolution

`MacLLMAgent.__init__` maps each string in `macllm_tools` to an attribute on the macllm.tools package. Unknown names fail at construction.

## Families (structural)

- General — e.g. time, web search.
- Files — Mount-point-scoped note tools: semantic search, read/write, move/delete, folder management, and path resolution (see [file_plugin.md](file_plugin.md)).
- Calendar — EventKit-backed read/write helpers (see [calendar.md](calendar.md)).
- Email — Read-only access to the local Superhuman mailbox via `shmail`: inbox, sent, starred, search, thread reading, split inboxes, contacts, and profiles.
- Skills — `read_skill` loads markdown skill bodies for the model (see [skills.md](skills.md)).
- Memory — `remember` appends to a daily markdown file for long-term recall.

## Threading and conversation context

Tools run on agent background threads. They access the current conversation through `get_current_conversation()` from `macllm/core/context.py`, which uses a thread-local to route to the correct conversation. Tools are completely unaware of multi-threading — they call the same functions regardless of how many agents are running.

## Side effects

Tools that need user approval (e.g., `run_command`) set `conversation.pending_approval` and block until the user decides. This is the only point where a tool blocks on user interaction. See `specs/shell.md` and `specs/parallel_tabs.md` for the approval flow.

## Boundaries

Tools are not tag plugins. User @ expansion happens before the agent; tools operate on the expanded task and return string observations to the agent loop.

Current export surface: see macllm/tools/__all__ for the authoritative name list.
