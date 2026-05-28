# Tools

## Overview

Tools are the callable operations exposed to agents.

They are implemented under `macllm/tools/`, exported from `macllm/tools/__init__.py`, and referenced by agents symbolically through tool-name strings.

## Design

The main design choice is that tools are the operational boundary of the agent system.

- agents decide what work to do
- tools perform the concrete work
- tool names are the stable contract between agent configuration and implementation

Tools return human-readable strings. smolagents records each model-planned tool call in `agent.memory.steps` (`ActionStep` entries), which the UI renders as **Steps**. Separately, tools wrapped with `@macllm_tool` (see `macllm/tools/_debug.py`) append transient human-readable lines to `conversation.tool_calls` while a tool body runs; `set_tool_message` updates the latest line. That list is cleared when a new agent run starts on the conversation.

## Tool Families

The current tool set is organized by domain:

- general utilities such as web search and web page fetch
- note/file tools for local notes under mount-point directories: search, read, create, append, modify, move, delete notes; create/delete subfolders; list and find folders; resolve mount-relative paths to absolute paths (see [file_plugin.md](file_plugin.md))
- calendar tools for scheduling and event lookup
- Things tools for task management
- skill tools such as `read_skill`
- email tools for read-only access to the local Superhuman mailbox via shmail
- memory tools for long-term agent recall

Files and calendar have deeper subsystem docs because they combine tools with additional indexing or agent structure. The rest of the tool layer is intentionally lightweight.

# Tools (agent API)

Exported tools are registered with smolagents using `@macllm_tool`, a thin wrapper around smolagents `tool` that adds debug logging and the live `conversation.tool_calls` behavior above. Only `_debug.py` imports `smolagents.tool` directly. Tools are referenced by name on each `MacLLMAgent` (`macllm_tools`).

## Resolution

`MacLLMAgent.__init__` maps each string in `macllm_tools` to an attribute on the macllm.tools package. Unknown names fail at construction.

## Families (structural)

- General — e.g. web search and web page fetch.
- Files — Mount-point-scoped note tools: semantic search, read/write, move/delete, folder management, and path resolution (see [file_plugin.md](file_plugin.md)).
- Calendar — EventKit-backed read/write helpers (see [calendar.md](calendar.md)).
- Email — Read-only access to the local Superhuman mailbox via `shmail`: inbox, sent, starred, search, thread reading, split inboxes, contacts, and profiles.
- Skills — `read_skill` loads markdown skill bodies for the model (see [skills.md](skills.md)).
- Memory — `remember` appends to a daily markdown file for long-term recall.

## Threading and conversation context

Tools run on agent background threads. They resolve the owning `Conversation` through `get_current_conversation()` from `macllm/core/context.py`. Resolution order: optional explicit `conv_id` (string UUID on each conversation, looked up in a small process-wide registry), else the thread-local set at agent thread entry via `set_current_conversation`, else `MacLLM._instance.chat_history` for main-thread callers such as tag plugins. The `@macllm_tool` wrapper captures `conv_id` at invocation time so `set_tool_message` targets the correct tab even when the UI focus changes. Tools do not manage threading themselves.

## Side effects

Tools that need user approval (e.g., `run_command`) set `conversation.pending_approval` and block until the user decides. This is the only point where a tool blocks on user interaction. See `specs/shell.md` for the approval flow. For `run_command`, the redundant live `tool_calls` row is removed while the inline approval UI is shown, then re-added after approval before sandboxed execution.

## Boundaries

Tools are not tag plugins. User @ expansion happens before the agent; tools operate on the expanded task and return string observations to the agent loop.

Current export surface: see macllm/tools/__all__ for the authoritative name list.

## Web Search And Fetch

`web_search(queries)` searches Brave and returns compact results. Each result with a URL is registered on the current `Conversation` and shown to the agent as a synthetic reference such as `web://example.com/1`, plus the result title and snippet. The real URL is stored privately in the conversation registry and is not returned in the search output.

`web_fetch(ref, start=0)` resolves a `web://...` reference, fetches the real URL, extracts readable HTML text, and returns at most 10,000 characters from the zero-based `start` offset. Cleaned page text is cached on the registry entry after the first fetch so later chunks are stable and avoid repeated downloads. Stored cleaned text is capped at 100,000 characters per page.

If a fetch result is not complete, it begins with a compact range marker:

```text
[page truncated, chars 0-10000 of 84321]
```

The next chunk starts at the end of the displayed range, for example `web_fetch("web://example.com/1", start=10000)`.
