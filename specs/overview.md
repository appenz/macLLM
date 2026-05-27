# MacLLM Overview

**INPORTANT:** 
Before writing any code or making architecture decisions, read:

1. This Overview spec
2. Any relevant specs in the `specs/` folder.
3. If you are writing tests, any relevant spec in the `test/specs` folder

MacLLM is a macOS-native LLM assistant written in Python with a Cocoa UI through PyObjC.
The application is organized around an agent runtime, a plugin-based request expansion layer,
and a small set of domain tools for file, web, skill, and calendar work.

This document is the architectural entry point for the codebase.

## Key Concept

MacLLM is structured as a number of conversations , each rendered by the UI in a tab. 

- The `UI` is a passive renderer for the `conversation`:
  - The `UI` reads the `conversation` object and renders it via Cocoa
  - The `UI` passes user requests to the `agent` via the a queue in the `conversation`
  - `Tools` that need approval for actions, add an approval request to the `conversation`
- Each `conversation` has exactly one supervising `agent` 
  - It can invoke `tools`
  - It can call `subagents`

Each agents is a separate thread. The UI is a separate thread as well.

## Main Runtime Flow

At a high level, the flow is as follows:

1. The user submits a query via the UI, which queues it via `conversation.submit(query)`.
2. The `conversation` checks its queue, and fetches the new `query`
3. User-invocable slash skill mentions are expanded by `SkillsRegistry`.
4. A `UserRequest` scans the prompt for `@...` and `/...` tokens and dispatches them to tag plugins. All slash commands (including `/reload` and `/reindex`) are handled as tag plugins at this stage.
5. The original prompt is stored in the conversation for UI/history.
6. If the expanded prompt is non-empty, it is passed to the supervising agent of the conversation
7. The agent calls tools and managed subagents as needed.
8. Tool progress is shown from `agent.memory.steps` (smolagents steps) and, for `@macllm_tool` wrappers, from transient `conversation.tool_calls` lines while tools execute.
9. The final assistant response is appended to the conversation and persisted.

## Key Objects

- `MacLLM`: application bootstrap and global resource holder. Owns runtime config, UI, conversation history, and plugin instances. Not in the request processing path — the UI calls `conversation.submit()` directly.
- `Conversation`: a self-contained chat session with its own agent runtime. Entry point: `submit(query)`. Owns UI/history messages, context pills, speed, agent class, live agent instance, agent thread, abort event, token metadata, pending approval, and query queue. Handles tag expansion, agent creation, and the full request lifecycle.
- `ConversationHistory`: container for `Conversation` objects. Tracks which conversation is active via `active_index`.
- `UserRequest`: ephemeral per-request object. Tracks the original prompt, expanded prompt, attached images, selected speed, and selected agent. Handles token scanning and plugin dispatch via `process_tags()`.

## Parallel Tab Execution

Multiple conversations can run agents simultaneously. Each conversation owns its own agent thread,
abort event, token metadata, and pending approval state. `MacLLM` holds no per-run state; it is
purely a bootstrap and global resource container.

Tools resolve the owning conversation through `get_current_conversation()` (`macllm/core/context.py`):
explicit `conv_id` registry lookup, then thread-local context set on the agent thread, then the
active-tab `chat_history` for main-thread callers.

The UI is a pure renderer of conversation state. The only signal from agent to UI is a generic
repaint callback. Tab switching, queues, and submit flow are described in `specs/conversation.md`.

## Subsystems

### UI

The Cocoa UI in `macllm/ui/` handles window lifecycle, conversation rendering, status display,
input, pills, autocomplete, and history browsing. See `specs/ui.md`.

### Request Expansion

The request expansion layer combines markdown-based skills with plugin-based `@...` and `/...`
expansion. Skills are loaded by `macllm/core/skills.py`; plugins live under `macllm/tags/`
and are discovered dynamically from `*_tag.py`. See `specs/skills.md` and `specs/tag_plugins.md`.

### Agents

The agent system lives under `macllm/agents/` and `macllm/core/agent_service.py`.

MacLLM agents are built on top of smolagents `ToolCallingAgent`.

The agent layer provides registry/autodiscovery, a thin factory, prompt template selection,
custom instructions, symbolic tool registration, and managed-agent delegation. See `specs/agents.md`.

Each agent’s system prompt includes the user’s current local time (with IANA time zone) and
approximate location (coordinates plus reverse-geocoded text when available), assembled by
`macllm/core/device_context.py` — not via a tool.

### Tools

Agent tools live under `macllm/tools/` and are re-exported from `macllm/tools/__init__.py`.

Tools are called by agents, not directly by the UI. They are grouped by domain, for example
general utilities, web lookup, file operations, calendar operations, and skill access.
See `specs/tools.md`, `specs/file_plugin.md`, and `specs/calendar.md`.

### LLM Integration

Via LiteLLM integration in `macllm/core/llm_service.py`.

- runtime config provides API keys
- `refresh_models()` builds a `MODELS` map for speed tiers (`slow` / `normal` / `fast`)
- the main runtime path goes through smolagents agents, not through direct `generate()` calls

### Persistence

Persistence lives in `macllm/core/memory.py`.

Persists conversation messages, active agent name, and the agent memory step list.
This allows the last conversation to be restored between runs.

## Configuration

Runtime configuration is loaded from project and user `config.toml` files. It provides API keys,
skill directories, and named mount points for indexed note directories (see `specs/file_plugin.md`).
The current model IDs are configured in code, not in TOML.

## Code Map

- `macllm/macllm.py`: application bootstrap, global config, and runtime entry point
- `macllm/core/`: conversation state, request processing, config, persistence, skills, agent services, status
- `macllm/agents/`: top-level agents, managed agents, prompt templates, registry
- `macllm/tags/`: tag plugin implementations
- `macllm/tools/`: agent tool implementations
- `macllm/ui/`: Cocoa UI
- `macllm/markdown/`: assistant markdown rendering
- `macllm/utils/`: support utilities such as screenshot capture

## Running and Testing

Run and test the project through `make` targets. The repository includes targets for normal  
execution, local tests, external-model tests, calendar-specific tests, and render/debug workflows.  

To test macLLM with a specific query, use the `debug-render` Makefile target. Don't ask the user to enter a query.