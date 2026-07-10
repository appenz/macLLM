# Tools

## Overview

Tools are the callable operations exposed to agents.

They are implemented under `macllm/tools/`, exported from `macllm/tools/__init__.py`, and referenced by agents symbolically through tool-name strings.

## Design

The main design choice is that tools are the operational boundary of the agent system.

- agents decide what work to do
- tools perform the concrete work
- tool names are the stable contract between agent configuration and implementation
- tools are the only way external data reaches an agent after a user request starts

Tools return observations. A plain string is a text observation. Tools may also return image-bearing observations through the macLLM tool-result path when the model needs to see an image. smolagents records each model-planned tool call in `agent.memory.steps` (`ActionStep` entries), which the UI renders as **Steps**. Separately, tools wrapped with `@macllm_tool` (see `macllm/tools/_debug.py`) append transient human-readable lines to `conversation_log` tool-call entries while a tool body runs; `set_tool_message` updates the latest line. Those entries are cleared when a new agent run starts on the conversation.

## Tool Families

The current tool set is organized by domain:

- general utilities such as web search and web page fetch
- note/file tools for local notes under mount-point directories: search, read, create, append, modify, move, delete notes; create/delete subfolders; list and find folders; resolve mount-relative paths to absolute paths (see [file_plugin.md](file_plugin.md))
- direct local-source tools such as `read_clipboard`, `read_file`, `capture_selection`, and `capture_window`
- calendar tools for scheduling and event lookup
- Things tools for task management
- skill tools such as `read_skill`
- email tools for read-only access to the local Superhuman mailbox via shmail
- memory tools for long-term agent recall

Files and calendar have deeper subsystem docs because they combine tools with additional indexing or agent structure. The rest of the tool layer is intentionally lightweight.

# Tools (agent API)

Exported tools are registered with smolagents using `@macllm_tool`, a thin wrapper around smolagents `tool` that adds debug logging and the live `conversation_log` tool-call behavior above. Only `_debug.py` imports `smolagents.tool` directly. Tools are referenced by name on each `MacLLMAgent` (`macllm_tools`).

## Resolution

`MacLLMAgent.__init__` maps each string in `macllm_tools` to an attribute on the macllm.tools package. Unknown names fail at construction.

## Families (structural)

- General — e.g. web search and web page fetch.
- Files — general local file reads via `read_file`, plus mount-point-scoped note tools: semantic search, read/write, move/delete, folder management, and path resolution (see [file_plugin.md](file_plugin.md)).
- Local device — clipboard and screenshot tools such as `read_clipboard`, `capture_selection`, and `capture_window`.
- Calendar — EventKit-backed read/write helpers (see [calendar.md](calendar.md)).
- Email — Read-only access to the local Superhuman mailbox via `shmail`: inbox, sent, starred, search, thread reading, split inboxes, contacts, and profiles.
- Skills — `read_skill` loads markdown skill bodies for the model (see [skills.md](skills.md)).
- Memory — `remember` appends to a daily markdown file for long-term recall.

## Threading and owning conversation

Tools run on agent background threads. They resolve the owning `Conversation` through the shared conversation resolver. Resolution order: optional explicit `conv_id` (string UUID on each conversation, looked up in a small process-wide registry), else the agent-thread binding, else `MacLLM._instance.chat_history` for main-thread callers. The `@macllm_tool` wrapper captures `conv_id` at invocation time so `set_tool_message` targets the correct tab even when the UI focus changes. Tools do not manage threading themselves.

## Side effects

Tools that need user approval (e.g., `run_command`) set `conversation.pending_approval` and block until the user decides. This is the only point where a tool blocks on user interaction. See `specs/shell.md` for the approval flow. For `run_command`, the redundant live `tool_calls` row is removed while the inline approval UI is shown, then re-added after approval before sandboxed execution.

## Boundaries

Tools are not tag plugins. Tag plugins may rewrite user shorthand before the agent runs, but they do not read external data. Tools operate during the agent loop and return observations to the agent loop.

Current export surface: see macllm/tools/__all__ for the authoritative name list.

## Observations

Every tool call returns one observation.

- A text-only observation may be a plain string.
- An image-bearing observation contains human-readable text plus one or more images for the next model step.
- The agent receives observations only through the tool-call loop. Initial user requests do not carry attached files, attached images, or preloaded text payloads.
- Existing string-returning tools remain valid and are treated as text-only observations.

## Sources

Tools that directly read an external item may add a Source for UI display. Only direct reads count: search, listing, discovery, folder traversal, and result enumeration do not add Sources. Sources are display metadata only; they do not affect tool execution or model input.

## Web Search And Fetch

`web_search(queries)` searches Brave and returns compact results with titles, snippets, and URLs or short fetchable references.

`web_fetch(url_or_ref, start=0)` fetches the requested page, extracts readable HTML text, and returns at most 10,000 characters from the zero-based `start` offset. Fetching a page is a direct read and adds a web Source. Merely seeing a URL in search results does not add a Source.

If a fetch result is not complete, it begins with a compact range marker:

```text
[page truncated, chars 0-10000 of 84321]
```

The next chunk starts at the end of the displayed range, for example `web_fetch("web://example.com/1", start=10000)`.
