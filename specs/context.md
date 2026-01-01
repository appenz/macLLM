# Context Overview

A conversation with the LLM can have context items. A context item is added when the user references an external source (e.g., `@clipboard`, `@file`) or when a tool fetches relevant data.

## How Context Works

When a user includes a context tag like `@clipboard` in their message:

1. The tag plugin fetches the content (clipboard text, file contents, etc.)
2. The content is embedded directly in the user message using a structured format
3. The original tag is preserved in display metadata for UI rendering

### Context Format in Messages

Context is embedded in the message content:

```
--- context:clipboard ---
Actual clipboard content here
--- end context:clipboard ---
```

Example flow:
- User types: `Summarize the text in @clipboard`
- Message stored with expanded content including the context block
- UI displays: `Summarize the text in @clipboard` (from display metadata)

## Context Tracking for UI

The Conversation maintains a `context_history` list for UI display purposes (context pills in the top bar):

```python
context_history = [
    {
        "name": "clipboard",
        "source": "clipboard",
        "type": "clipboard",
        "context": "Hello world",
        "icon": ""
    },
]
```

This is separate from the messages array and used only for:
- Rendering context pills in the UI top bar
- Showing previews of context content
- Tracking what external sources have been referenced

## Context Lifetime

- Context is embedded in the specific user message where it was referenced
- Since the full message history is sent to the LLM, context remains available for the entire conversation
- When a new conversation starts, there is no prior context

## Context Names

When context is added, a unique name is assigned:
- First clipboard reference becomes `clipboard`
- If a name already exists, a suffix is added: `clipboard-1`, `clipboard-2`
- Names are used in the context block markers
