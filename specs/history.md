# macLLM Conversation History & Messages

## Key Concepts

- **Message** - A single turn in a conversation (user input, assistant response, or system prompt)
- **Conversation** - A series of messages in OpenAI-compatible format, plus agent state and context tracking
- **ConversationHistory** - The collection of all previous Conversations

## Message Format

Messages follow the OpenAI chat completions format:

```python
{"role": "user", "content": "Summarize \n\n--- context:clipboard ---\nHello world\n--- end context:clipboard ---"}
{"role": "assistant", "content": "The clipboard contains a greeting."}
{"role": "system", "content": "You are a helpful assistant..."}
```

### Message Roles

| Role | Sent to LLM | Shown in UI | Description |
|------|-------------|-------------|-------------|
| `system` | Yes | No | System prompt, instructions for the LLM |
| `user` | Yes | Yes | User input |
| `assistant` | Yes | Yes | LLM responses |

## Conversation Class

A Conversation maintains messages in OpenAI-compatible format, context tracking for the UI, and agent state.

### Messages Array

Pure OpenAI format that can be passed directly to LiteLLM or agent frameworks:

```python
self.messages = [
    {"role": "system", "content": "You are a helpful assistant..."},
    {"role": "user", "content": "Summarize this\n\n--- context:clipboard ---\nHello world\n--- end context:clipboard ---"},
    {"role": "assistant", "content": "The text says hello world."},
]
```

### Attributes

```python
class Conversation:
    messages: list[dict]              # OpenAI-format message list
    context_history: list[dict]       # Context entries for UI pills
    speed_level: str                  # Current speed level (default "normal")
    agent: MacLLMAgent | None         # Current agent instance
    agent_cls: type | None            # Agent class (set lazily)
    ui_update_callback: Callable | None
```

### Message Management

- `add_user_message(content: str)`: Add a user message
- `add_assistant_message(content: str)`: Add assistant response
- `add_system_message(content: str)`: Add/update system prompt (typically only at conversation start)

### For UI Display

- `get_displayable_messages() -> list[dict]`: Returns only user/assistant messages

### Context Tracking (for UI pills)

- `context_history`: List tracking context sources for UI display
- `add_context(suggested_name, source, context_type, context, icon=None) -> str`: Register context for UI pills; returns the actual name used (deduplicates by source)
- `has_path_in_context(path: str) -> bool`: Check if a file path was already referenced in this conversation's context

### Agent Management

- `_get_agent_cls()`: Lazily resolves the agent class (defaults to `get_default_agent_class()`)
- `_create_agent(token_callback=None)`: Creates an agent instance via `agent_service.create_agent()`

### General

- `reset(clear_persisted=False)`: Clear messages and metadata, restore default welcome message. If `clear_persisted` is True, also clears persisted conversation data.

## Context Embedding

Context (files, clipboard, URLs) is embedded directly in the user message content:

```
User types: "Summarize @clipboard"

Stored in messages as:
{
    "role": "user", 
    "content": "Summarize \n\n--- context:clipboard ---\nActual clipboard text here\n--- end context:clipboard ---"
}
```

## UserRequest Class

Ephemeral object that processes a single user input:

```python
class UserRequest:
    def __init__(self, original_prompt: str):
        self.original_prompt = original_prompt  # What user typed
        self.expanded_prompt = original_prompt  # After tag expansion (context embedded)
        self.context = ""                       # Additional context to append
        self.needs_image = False                # Whether image generation is needed
        self.images = []                        # PIL Images (e.g. clipboard images)
        self.speed_level = None                 # Speed preference if /fast, /slow used
        self.agent_name = None                  # Agent type if @agent: tag used
```

### Methods

- `find_shortcuts(text: str) -> list[tuple[int, int, str]]`: Class method. Finds all `@tags` and `/commands` in the text and returns `(start_pos, end_pos, tag_text)` tuples.
- `process_tags(plugins, conversation, ...)`: Scans `expanded_prompt` for tags/commands, calls each matching plugin's `expand()`, and replaces the tag in-place with the returned string.

## ConversationHistory

Container for all conversations:

```python
class ConversationHistory:
    conversations: list[Conversation]
    
    def add_conversation(self, conversation=None) -> Conversation
    def get_current_conversation() -> Conversation
```

## Persistence

Conversation state can be persisted via `macllm/core/memory.py`:

- `save_conversation(conversation)`: Persist conversation to disk
- `load_conversation() -> Conversation | None`: Load persisted conversation
- `clear_conversation()`: Remove persisted data

The `Conversation.reset(clear_persisted=True)` method calls `clear_conversation()` when clearing persisted state.

## Notes

- **System prompt**: Stored as first message in messages array with role "system"
