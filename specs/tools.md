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

Tools return observations. A plain string is a text observation. A tool may also return a PIL image; `@macllm_tool` turns that into a short text observation and queues the image for `ActionStep.observations_images` so a vision model can see it. smolagents records each model-planned tool call in `agent.memory.steps` (`ActionStep` entries) for runtime/debug history. Separately, tools wrapped with `@macllm_tool` (see `macllm/tools/_debug.py`) append transient human-readable lines to `conversation_log` before a tool body runs; `set_tool_message` updates the latest line. The regular UI passively renders the latest such line as its ephemeral operation instead of showing historical Steps. These entries are cleared at run boundaries.

## Tool Families

The current tool set is organized by domain:

- general utilities such as web search and web page fetch
- virtual filesystem tools for reading, writing, appending, listing, copying, deleting, and
  creating directories, plus semantic note discovery through `search_notes` (see
  [filesystem.md](filesystem.md))
- direct local-source tools such as `read_clipboard`
- calendar tools for scheduling and event lookup
- Things tools for task management
- skills loaded from `/skills` with `read_file`
- email tools for read-only access to the local Superhuman mailbox via shmail
- long-term memory files under `/memory`

Files and calendar have deeper subsystem docs because they combine tools with additional indexing or agent structure. The rest of the tool layer is intentionally lightweight.

# Tools (agent API)

Exported tools are registered with smolagents using `@macllm_tool`, a thin wrapper around smolagents `tool` that adds debug logging and the live `conversation_log` tool-call behavior above. Only `_debug.py` imports `smolagents.tool` directly. Tools are referenced by name on each `MacLLMAgent` (`macllm_tools`).

## Resolution

`MacLLMAgent.__init__` maps each string in `macllm_tools` to an attribute on the macllm.tools package. Unknown names fail at construction.

## Families (structural)

- General — e.g. web search and web page fetch.
- Files — one virtual filesystem shared by all file operations; indexed mounts additionally support
  autocomplete and semantic note search (see [filesystem.md](filesystem.md) and
  [file_plugin.md](file_plugin.md)).
- Local device — clipboard via `read_clipboard` (text or image).
- Calendar — EventKit-backed read/write helpers (see [calendar.md](calendar.md)).
- Email — Read-only access to the local Superhuman mailbox via `shmail`: inbox, sent, starred, search, thread reading, split inboxes, contacts, and profiles.
- Skills — agents receive a catalog and load skill files from `/skills` (see [skills.md](skills.md)).
- Memory — agents read and write long-term memory files under `/memory`.

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
- An image observation is a PIL image return from the tool; `@macllm_tool` queues it for the next model step via `observations_images`.
- The agent receives observations only through the tool-call loop. Initial user requests do not carry attached files, attached images, or preloaded text payloads.
- Existing string-returning tools remain valid and are treated as text-only observations.

## Sources

Tools that directly read an external item may call `conversation.add_source(kind, ref)`. Only direct reads count: search, listing, discovery, folder traversal, and result enumeration do not add Sources. Sources are identity metadata only (`kind` + `ref`); they do not affect tool execution or model input, and the UI derives presentation from them.

## Web Search And Fetch

`web_search(query)` sends one search string to Brave and returns up to five compact results with titles, snippets, and real URLs. Each call counts as one of the 50 searches allowed per agent run.

`web_fetch(url, start=0)` fetches the requested page, extracts readable HTML text, and returns at most 10,000 characters from the zero-based `start` offset. Fetching a page is a direct read and adds a web Source. Merely seeing a URL in search results does not add a Source.

If a fetch result is not complete, it begins with a compact range marker:

```text
[page truncated, chars 0-10000 of 84321]
```

The next chunk starts at the end of the displayed range, for example `web_fetch("https://example.com/page", start=10000)`.
