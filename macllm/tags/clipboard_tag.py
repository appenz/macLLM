from .base import TagPlugin

class ClipboardTag(TagPlugin):
    """Expands @clipboard by adding the current clipboard text to conversation context."""

    def __init__(self, macllm):
        super().__init__(macllm)
        self.ui = macllm.ui

    def get_prefixes(self) -> list[str]:
        return ["@clipboard"]

    def expand(self, tag: str, conversation, request):
        # Retrieve clipboard contents via UI helper
        content = self.ui.read_clipboard()

        # Unique source name is clipboard-#
        # where # is the number of context entires in the chat history
        context_count = len(conversation.context_history)
        if context_count == 0:
            source_name = "clipboard"
        else:
            source_name = f"clipboard-{context_count}"

        # Store in conversation context
        context_name = conversation.add_context(
            "clipboard",            # suggested name
            source_name,            # source (constant)
            "clipboard",            # context type
            content,                # actual text
            icon="📋",
        )
        # Replace tag with the context name (e.g. CLIPBOARD_CONTENTS or with -1 suffix)
        return f"RESOURCE:{context_name}" 
    
    def display_string(self, suggestion: str) -> str:
        return "📋" + suggestion