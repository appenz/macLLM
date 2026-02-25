from .base import TagPlugin

class ClipboardTag(TagPlugin):
    """Expands @clipboard by adding the current clipboard text or image to conversation context."""

    def __init__(self, macllm):
        super().__init__(macllm)
        self.ui = macllm.ui

    def get_prefixes(self) -> list[str]:
        return ["@clipboard"]

    def expand(self, tag: str, conversation, request):
        context_count = len(conversation.context_history)
        if context_count == 0:
            source_name = "clipboard"
        else:
            source_name = f"clipboard-{context_count}"

        image = self.ui.read_clipboard_image()
        if image is not None:
            request.images.append(image)

            context_name = conversation.add_context(
                "clipboard",
                source_name,
                "image",
                "[image]",
                icon="🖼️",
            )
            return f"\n\n[Attached image from clipboard]"

        content = self.ui.read_clipboard()

        context_name = conversation.add_context(
            "clipboard",
            source_name,
            "clipboard",
            content,
            icon="📋",
        )
        return f"\n\n--- context:{context_name} ---\n{content}\n--- end context:{context_name} ---" 
    
    def display_string(self, suggestion: str) -> str:
        return "📋" + suggestion
