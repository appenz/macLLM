# macLLM Plugin Architecture Specification

## Base Plugin Class

```python
class TagPlugin:
    # Required hooks
    def get_prefixes(self) -> list[str]:  # e.g. ["@http://", "@https://", "@~"]
    def expand(self, tag: str, conversation: Conversation, request: UserRequest) -> str:
    # Optional config-time hooks (processed while reading shortcut files)
    def get_config_prefixes(self) -> list[str]:
    def on_config_tag(self, tag: str, value: str) -> None:
    # Optional dynamic-autocomplete hooks (for UI suggestions)
    def supports_autocomplete(self) -> bool:
    def autocomplete(self, fragment: str, max_results: int = 10) -> list[str]:
    def display_string(self, suggestion: str) -> str:
    # Optional catch-all autocomplete hook
    def match_any_autocomplete(self) -> bool:
```

## Plugin Examples

- **URLTag**: handles `@http://`, `@https://` → fetches web content, embeds in message
- **FileTag**: config tag `@IndexFiles` indexes directories; `@path` references embed file contents; `/reindex` rebuilds the index
- **ClipboardTag**: handles `@clipboard` → gets clipboard content (text or image), embeds in message
- **ImageTag**: handles `@selection`, `@window` → captures screenshots for image analysis
- **SpeedTag**: handles `/fast`, `/slow`, `/think` → sets speed preference for the request
- **AgentTag**: handles `@agent:<name>` → selects which agent runs the conversation (with autocomplete)

## Context Embedding

Plugins that add context should:

1. Fetch the content (file, URL, clipboard, etc.)
2. Add to conversation's context_history (for UI pills)
3. Return the context block to embed in the message:

```python
def expand(self, tag: str, conversation: Conversation, request: UserRequest) -> str:
    content = self.fetch_content(tag)
    name = conversation.add_context(
        suggested_name="clipboard",
        source="clipboard",
        context_type="clipboard",
        context=content
    )
    return f"\n\n--- context:{name} ---\n{content}\n--- end context:{name} ---"
```

## Integration

- Main MacLLM class maintains list of registered plugins
- `handle_instructions()` creates UserRequest, passes to plugins via `process_tags()`
- Plugins return replacement strings that get embedded in the message content

## LLM Service

LLM calls are handled by `llm_service.py` which wraps LiteLLM:

```python
from macllm.core.llm_service import generate

response, metadata = generate(
    messages=conversation.messages,
    speed="normal"
)
```

Speed levels map to LiteLLM model strings:
- `fast` → `openai/mercury` (Inception Labs)
- `normal` → `gemini/gemini-3-flash-preview` (Google)
- `slow` → `gpt-5` (OpenAI)
