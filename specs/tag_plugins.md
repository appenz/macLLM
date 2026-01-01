# macLLM Plugin Architecture Specification

## Base Plugin Class

```python
class MacLLMPlugin:
    # Required hooks
    def get_prefixes(self) -> list[str]:  # e.g. ["@http://", "@https://", "@~"]
    def expand(self, tag: str, request: UserRequest) -> None:
    # Optional config-time hooks (processed while reading shortcut files)
    def get_config_prefixes(self) -> list[str]:
    def on_config_tag(self, tag: str, value: str) -> None:
    # Optional dynamic-autocomplete hooks (for UI suggestions)
    def supports_autocomplete(self) -> bool:
    def autocomplete(self, fragment: str, max_results: int = 10) -> list[str]:
    def display_string(self, suggestion: str) -> str:
```

## Plugin Examples

- **URLTag**: handles `@http://`, `@https://` → fetches web content, embeds in message
- **FileTag**: config tag `@IndexFiles` indexes directories; `@path` references embed file contents
- **ClipboardTag**: handles `@clipboard` → gets clipboard content, embeds in message
- **SpeedTag**: handles `/fast`, `/slow`, `/think` → sets speed preference for the request

## Context Embedding

Plugins that add context should:

1. Fetch the content (file, URL, clipboard, etc.)
2. Add to conversation's context_history (for UI pills)
3. Return the context block to embed in the message:

```python
def expand(self, tag: str, conversation, request) -> str:
    content = self.fetch_content(tag)
    name = conversation.add_context(
        suggested_name="clipboard",
        source="clipboard",
        context_type="clipboard",
        context=content
    )
    # Return context block that gets embedded in the user message
    return f"\n\n--- context:{name} ---\n{content}\n--- end context:{name} ---"
```

## Integration

- Main MacLLM class maintains list of registered plugins
- `handle_instructions()` creates UserRequest, passes to plugins via `process_tags()`
- Plugins return replacement strings that get embedded in the message content
- Display metadata preserves the original user input (with @tags visible)

## LLM Service

LLM calls are handled by `llm_service.py` which wraps LiteLLM:

```python
from macllm.core.llm_service import generate

response, metadata = generate(
    messages=conversation.get_messages_for_llm(),
    speed="normal"
)
```

Speed levels map to LiteLLM model strings:
- `fast` → Fast/cheap model
- `normal` → Default balanced model  
- `slow` → High-capability model with reasoning
