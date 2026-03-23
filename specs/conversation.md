# Conversation State

## Overview

Conversation state in macLLM is split across three layers:

- persistent conversation state in `Conversation`
- transient per-request expansion state in `UserRequest`
- agent execution state in `agent.memory.steps`

This split is the main architectural decision in the subsystem. The UI-visible conversation, the
expanded prompt, and the internal agent trace are related, but they are not the same object.

## Conversation Model

`Conversation` in `macllm/core/chat_history.py` is the durable state for the active chat session.

It stores:

- `messages` for user-visible conversation history
- `context_history` for context pills and previews
- `speed_level`
- `agent_cls`
- `agent`

`ConversationHistory` is a thin container for `Conversation` objects. The current runtime uses the most recent conversation as the active one.

## Request vs Stored History

The current runtime does not store the expanded prompt as the user message.

The flow is:

1. `MacLLM.handle_instructions()` receives the original prompt.
2. Skills and tag plugins expand that prompt into `UserRequest.expanded_prompt`.
3. The original prompt is appended to `Conversation.messages`.
4. The agent runs on `request.expanded_prompt`.

This means `Conversation.messages` is primarily UI/history state, not the exact payload sent to the agent.

## Context State

Context added by plugins is tracked separately from message history.

- `Conversation.context_history` stores named context entries for UI pills and previews
- `Conversation.add_context(...)` deduplicates by source and returns the actual context name
- plugins may also embed that context into `UserRequest.expanded_prompt`

This keeps UI context management separate from stored chat text.

## Agent State

Each `Conversation` owns an agent instance and its selected agent class.

`Conversation._create_agent()` rebuilds the agent through `create_agent(...)` in `macllm/core/agent_service.py`.
When an agent is recreated, existing `agent.memory.steps` are preserved so the agent trace survives across re-instantiation within the same conversation.

## Persistence

Persistence lives in `macllm/core/memory.py`.

The persisted state is:

- `conversation.messages`
- `conversation.agent.memory.steps`
- the active agent name

This is enough to restore the visible conversation and the agent's accumulated execution history.
It does not persist `UserRequest`, which is intentionally per-request and ephemeral.
