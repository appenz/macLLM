from .base import TagPlugin

class ClipboardTag(TagPlugin):
    """Expands @clipboard by adding the current clipboard text or image to conversation context."""

    def __init__(self, macllm):
        super().__init__(macllm)
        self.ui = macllm.ui

    def get_prefixes(self) -> list[str]:
        return ["@clipboard"]

    def expand(self, tag: str, conversation, request):
        cached_context_name = getattr(request, "_clipboard_text_context_name", None)
        if cached_context_name:
            request.add_context_block(cached_context_name, getattr(request, "_clipboard_text_context", ""))
            return f"context:{cached_context_name}"

        context_count = len(conversation.context_history)
        if context_count == 0:
            source_name = "clipboard"
        else:
            source_name = f"clipboard-{context_count}"

        content = self.ui.read_clipboard()
        if content is not None:
            context_name = conversation.add_context(
                "clipboard",
                source_name,
                "clipboard",
                content,
                icon="📋",
            )
            request._clipboard_text_context_name = context_name
            request._clipboard_text_context = content
            request.add_context_block(context_name, content)
            return f"context:{context_name}"

        image = self.ui.read_clipboard_image()
        if image is not None:
            request.images.append(image)

            conversation.add_context(
                "clipboard",
                source_name,
                "image",
                "[image]",
                icon="🖼️",
            )
            return f"\n\n[Attached image from clipboard]"

        return tag
    
    def display_string(self, suggestion: str) -> str:
        return "📋" + suggestion
