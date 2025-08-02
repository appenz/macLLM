# macLLM Conversation History & Requests

## Key Concepts

- **Request** - An individual request to the LLM consisting of a prompt and response
- **Conversation** - A series of user inputs and LLM responses, plus context for these inputs
- **ConversationHistory** - The collection of all previous Conversations

## UserRequest Class

Gathers all the data for a single request to the LLM.

```python
class UserRequest:
    def __init__(self, original_prompt: str):
        self.original_prompt = original_prompt
        self.expanded_prompt = original_prompt  # Current working text
        self.context = ""                       # All the relevant text context for this request as a text string
        self.image = None                       # Image that is sent as part of this request, or None.
```

## Conversation

A Conversation object maintains two separate lists:

- **Chat history**: List of dicts with fields:
  - `role`: 'user' or 'assistant'
  - `text`: The unexpanded text as typed by user or response from assistant
  - `expanded_text`: The text with expanded shortcuts and expanded context references
  - `timestamp`: When the message was created

- **Context**: List of dicts with fields:
  - `name`: Unique identifier for this context block
  - `source`: Original source (file path, URL, etc.)
  - `type`: one of "url", "path", "clipboard", "image"
  - `context`: The actual content/context string

Context is not specific to a Request, but is for the conversation as a whole.

### Chat Methods

- `add_chat_entry(role, text, expanded_text)`: Adds conversation turn
- `get_chat_history_original()`: returns the unexpanded chat history to show the user as a string
- `get_chat_history_expanded()`: returns the fully expanded chat history for the LLM as a string

### Context Methods

- `add_context(suggested_name, source, type, context)`: Adds context entry, returns actual name
  - Will not add a duplicate, just return the correct name for the duplicate
- `get_context_history_text()`: Returns context history as one large string except images
- `get_context_last_image()`: Returns only the last image in the context history

### General Methods

- `reset()`: Clears both lists, restores default message

### Notes

- **Storage**: In-memory only, no persistence.
- **Images** are stored in the normal context list as type "image" but handled differently.
  - The reason is that the API of most LLMs can't accept an image as part of the main request but instead needs it as a POST because of this images are not automatically returned by `get_context_history_text()` in the large text block but via `get_context_last_image()`
  - Images are also stored and returned as binary for efficiency

## ConversationHistory

The ConversationHistory contains a list of Conversation objects. The current conversation is the last object in the list. 