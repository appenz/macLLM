# MacLLM Overview

**INPORTANT:** Before writing any code or making architecture decisions, read:

1. This Overview spec
2. Any relevant specs in the `specs/` folder.
3. If you are writing tests, any relevant spec in the `test/specs` folder

MacLLM is a macOS-native LLM assistant written in Python with a Cocoa UI through PyObjC. The application is organized around an agent runtime that uses tools and managed subagents to perform work. The UI is mostly a passive rendeder for the agent's conversation.

This document is the architectural entry point for the codebase.

## Key Concept

MacLLM is structured as a number of conversations, each rendered by the UI in a tab. 

- Each `conversation` has one Smolagents `agent` 
  - It can invoke `tools`
  - It can call `subagents`
  - Most conversation state is inside the agent itself
  - Additional UI relevant state is stored in the `ConversationLog`
- The `UI` is a purely passive renderer for the `conversation`:
  - The `UI` reads the `conversation` object and renders it via Cocoa
  - The `UI` passes user requests to the `agent` via the a queue in the `conversation`
  - `Tools` that need approval for actions, add an approval request to the `conversation`

Each agents is a separate thread. The UI is a separate thread as well.

## Main Runtime Flow

At a high level, the flow is as follows:

1. The user submits a query via the UI, which queues it via `conversation.submit(query)`.
2. The `conversation` checks its queue, and fetches the new `query`
3. User-invocable slash skill mentions are rewritten by `SkillsRegistry`. Skills may read predefined configured skill files because they are prompt assets.
4. A `UserRequest` applies input sugar such as `@...` and plugin-owned `/...` tokens. These rewrites are purely UI sugar to make the user's instruction more explicit or set run options; they do not perform actual tasks.
5. The rewritten prompt is passed to the supervising agent of the conversation.
6. The agent calls tools and managed subagents as needed. All external data access happens through tools, and tools return observations.
7. Tool progress is shown from `agent.memory.steps` (smolagents steps) and, for `@macllm_tool` wrappers, from transient `conversation_log` tool-call entries while tools execute.
8. Tools that directly read a source record that source on the conversation for the UI Sources strip.
9. The final assistant response is appended to the conversation and persisted.



## Key Objects

- `MacLLM`: application bootstrap and global resource holder. Owns runtime config, UI, conversation history, and plugin instances. Not in the request processing path — the UI calls `conversation.submit()` directly.
- `Conversation`: a self-contained chat session with its own agent runtime. Entry point: `submit(query)`. Owns UI/history messages, Sources metadata, speed, agent class, live agent instance, agent thread, abort event, token metadata, pending approval, and query queue. Handles tag rewriting, agent creation, and the full request lifecycle.
- `ConversationHistory`: container for `Conversation` objects. Tracks which conversation is active via `active_index`.
- `UserRequest`: ephemeral per-request object. Tracks the original prompt, rewritten prompt, selected speed, selected agent, and tool-disabling flags. Handles token scanning and plugin dispatch via `process_tags()`.



## Parallel Tab Execution

Multiple conversations can run agents simultaneously. Each conversation owns its own agent thread,
abort event, token metadata, and pending approval state. `MacLLM` holds no per-run state; it is
purely a bootstrap and global resource container.

Tools resolve the owning conversation through a conversation resolver:
explicit `conv_id` registry lookup, then the agent-thread binding, then the
active-tab `chat_history` for main-thread callers.

The UI is a pure renderer of conversation state. The only signal from agent to UI is a generic
repaint callback. Tab switching, queues, and submit flow are described in `specs/conversation.md`.

## Subsystems



### UI

The Cocoa UI in `macllm/ui/` handles window lifecycle, conversation rendering, status display,
input, pills, autocomplete, and history browsing. See `specs/ui.md`.

### Agents

The agent system lives under `macllm/agents/` and `macllm/core/agent_service.py`.

MacLLM agents are built on top of smolagents `ToolCallingAgent`.

The agent layer provides registry/autodiscovery, a thin factory, prompt template selection,
custom instructions, symbolic tool registration, and managed-agent delegation. See `specs/agents.md`.

Each agent’s system prompt includes the user’s current local time (with IANA time zone) and
approximate location (coordinates plus reverse-geocoded text when available), assembled by
the device situation helper — not via a tool.

### Tools

Agent tools live under `macllm/tools/` and are re-exported from `macllm/tools/__init__.py`.

Tools are called by agents, not directly by the UI. They are grouped by domain, for example
general utilities, web lookup, file operations, clipboard/screenshot operations, calendar operations, and skill access.
Tools are the only way external data reaches the agent after a user request starts.
See `specs/tools.md`, `specs/file_plugin.md`, and `specs/calendar.md`.

### Input Sugar

Input sugar is a UI convenience, not an execution layer. Skills are loaded by
`macllm/core/skills.py`; tag plugins live under `macllm/tags/` and are discovered
dynamically from `*_tag.py`.

Skills may rewrite `/skill` into predefined prompt assets. Tag plugins may rewrite shorthand
such as `@clipboard` into explicit tool-use instructions or set run options such as agent and
speed. Tag plugins do not read dynamic external data or attach payloads. See `specs/skills.md`
and `specs/tag_plugins.md`.

### LLM Integration

Via LiteLLM integration in `macllm/core/llm_service.py`.

- runtime config provides API keys
- `refresh_models()` builds a `MODELS` map for speed tiers (`slow` / `normal` / `fast`)
- the main runtime path goes through smolagents agents, not through direct `generate()` calls

### Persistence

Persistence lives in `macllm/core/persistence.py`.

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

To test macLLM with a specific query, use the `debug-render` Makefile target.   
For debugging, run macllm via the Makefile. Don't ask the user run macllm manually, or if you have to do this state explicitly why automatic invocation was not possible.