# MacLLM Overview

MacLLM is a macOS-native LLM assistant written in Python with a Cocoa UI through PyObjC.
The application is organized around an agent runtime, a plugin-based request expansion layer,
and a small set of domain tools for file, web, skill, and calendar work.

This document is the architectural entry point for the codebase.

## Main Runtime Flow

At a high level, a request moves through these stages:

1. The user enters text in the Cocoa UI.
2. `MacLLM.handle_instructions()` in `macllm/macllm.py` receives the original prompt.
3. Leading slash skill invocations are expanded by `SkillsRegistry`.
4. A `UserRequest` scans the prompt for `@...` and `/...` tokens and dispatches them to tag plugins.
5. Plugins may:
   - add context
   - select an agent
   - set the speed tier
   - attach images
   - rewrite or remove tokens in the expanded prompt
6. The original prompt is stored in the conversation for UI/history.
7. The expanded prompt is sent to a smolagents-based agent.
8. The agent calls tools and managed subagents as needed.
9. `AgentStatusManager` tracks the current plan and tool progress for live UI display.
10. The final assistant response is appended to the conversation and persisted.

## Key Objects

- `MacLLM`: application coordinator. Owns runtime config, UI, current conversation state, plugin instances, agent status, and model metadata. Main entry point: `handle_instructions(user_input)`.
- `Conversation`: active chat session. Stores UI/history messages, context pill state, speed, selected agent class, and the live agent instance. Recreates agents via `_create_agent()`.
- `ConversationHistory`: container for `Conversation` objects. The most recent conversation is the active one.
- `UserRequest`: ephemeral per-request object. Tracks the original prompt, expanded prompt, attached images, selected speed, and selected agent. Handles token scanning and plugin dispatch via `process_tags()`.
- `AgentStatusManager`: live execution state for an agent run, including current plan, tool calls, and managed-agent nesting. The UI reads it to render the status block.

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

- `macllm/macllm.py`: application coordinator and runtime entry point
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

Additional subsystem details live in the `specs/` folder.
