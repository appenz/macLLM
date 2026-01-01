# macLLM Conversation History & Messages

## Key Concepts

- **Message** - A single turn in a conversation (user input, assistant response, system prompt, or tool result)
- **Conversation** - A series of messages in OpenAI-compatible format, plus display metadata
- **ConversationHistory** - The collection of all previous Conversations

## Message Format

Messages follow the OpenAI chat completions format. The `content` field contains the **expanded** text (with context embedded), not the original user input:

```python
{"role": "user", "content": "Summarize \n\n--- context:clipboard ---\nHello world\n--- end context:clipboard ---"}
{"role": "assistant", "content": "The clipboard contains a greeting."}
{"role": "system", "content": "You are a helpful assistant..."}
{"role": "tool", "content": "..."}  # Future: for agentic features
```

The original user input (`"Summarize @clipboard"`) is stored separately in `display_metadata`.

### Message Roles

| Role | Sent to LLM | Shown in UI | Description |
|------|-------------|-------------|-------------|
| `system` | Yes | No | System prompt, instructions for the LLM |
| `user` | Yes | Yes | User input |
| `assistant` | Yes | Yes | LLM responses |
| `tool` | Yes | No | Tool/function call results (future) |

## Conversation Class

A Conversation maintains two parallel data structures:

### 1. Messages Array (OpenAI-compatible)

Pure OpenAI format that can be passed directly to LiteLLM or agent frameworks:

```python
self.messages = [
    {"role": "system", "content": "You are a helpful assistant..."},
    {"role": "user", "content": "Summarize this\n\n--- context:clipboard ---\nHello world\n--- end context:clipboard ---"},
    {"role": "assistant", "content": "The text says hello world."},
]
```

### 2. Display Metadata (keyed by content hash)

UI-specific data stored separately, linked by hash of message content:

```python
self.display_metadata = {
    "a1b2c3d4": {  # hash of role + content
        "display_content": "Summarize this @clipboard",  # Original user input before expansion
        "timestamp": 1234567890.0,
        "context_refs": ["clipboard"]  # For UI context pills
    },
    ...
}
```

The hash is computed as: `sha256(f"{role}:{content}")[:16]`

## UserRequest Class

Ephemeral object that processes a single user input:

```python
class UserRequest:
    def __init__(self, original_prompt: str):
        self.original_prompt = original_prompt  # What user typed
        self.expanded_prompt = original_prompt  # After tag expansion (context embedded)
        self.speed_level = None                 # Speed preference if /fast, /slow used
```

## Conversation Methods

### Message Management

- `add_user_message(display_content, expanded_content)`: Add user message, store display metadata
- `add_assistant_message(content)`: Add assistant response
- `add_system_message(content)`: Add/update system prompt (typically only at conversation start)

### For LLM Calls

- `get_messages_for_llm() -> list[dict]`: Returns pure OpenAI-format messages array

### For UI Display

- `get_displayable_messages() -> list[dict]`: Returns only user/assistant messages
- `get_display_content(message) -> str`: Returns original user input (before expansion) for a message

### Context Tracking (for UI pills)

- `context_history`: List tracking context sources for UI display
- `add_context(name, source, type, content)`: Register context for UI pills

### General

- `reset()`: Clear messages, restore default welcome message

## Context Embedding

Context (files, clipboard, URLs) is embedded directly in the user message content:

```
User types: "Summarize @clipboard"

Stored in messages as:
{
    "role": "user", 
    "content": "Summarize \n\n--- context:clipboard ---\nActual clipboard text here\n--- end context:clipboard ---"
}

Display metadata stores:
{
    "display_content": "Summarize @clipboard",
    ...
}
```

The UI shows "Summarize @clipboard" but the LLM receives the expanded version with actual content.

## ConversationHistory

Container for all conversations:

```python
class ConversationHistory:
    conversations: list[Conversation]
    
    def add_conversation(self) -> Conversation
    def get_current_conversation() -> Conversation
```

## Notes

- **Storage**: In-memory only, no persistence
- **System prompt**: Stored as first message in messages array with role "system"
