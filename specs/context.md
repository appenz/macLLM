# Context Representation

## Overview

Context is external data brought into a request, such as clipboard contents, file contents, URLs, or images.

In the current architecture, context has three related pieces:

- structured context state in `Conversation.context_history`
- per-request context blocks collected on `UserRequest`
- embedded context appended to the expanded prompt

This split is deliberate. The UI needs named context entries for pills and previews, while the agent needs inline context in the expanded prompt.

## Context Flow

When a plugin adds context:

1. it fetches or generates the external content
2. it registers that content with `Conversation.add_context(...)`
3. it adds the full context block to `UserRequest`
4. it returns a short inline reference such as `context:clipboard`
5. after all tags are processed, `UserRequest.process_tags()` appends the collected context blocks once at the end of the expanded prompt

The original prompt remains the user-visible message stored in conversation history.

## Context State

`Conversation.context_history` stores one entry per context source, including:

- a display name
- the original source identifier
- the context type
- the context payload
- an optional icon

`Conversation.add_context(...)` deduplicates by source and assigns a stable name, adding a numeric suffix when needed.

## Context Lifetime

Context belongs to the conversation in which it was added.

- it remains available in `context_history` for UI rendering
- the embedded form remains part of the expanded prompt for that request, appended after the user-facing instruction text
- a new conversation starts with no prior context
