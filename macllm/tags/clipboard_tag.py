from .base import TagPlugin

class ClipboardTag(TagPlugin):
    """Expands @clipboard by adding the current clipboard text to conversation context."""

    def __init__(self, macllm):
        super().__init__(macllm)
        self.ui = macllm.ui

    def get_prefixes(self) -> list[str]:
        return ["@clipboard"]

    def expand(self, tag: str, conversation):
        # Retrieve clipboard contents via UI helper
        content = self.ui.read_clipboard()
        # Store in conversation context
        context_name = conversation.add_context(
            "clipboard",            # suggested name
            "clipboard",            # source (constant)
            "clipboard",            # context type
            content,                 # actual text
            icon="📋",
        )
        # Replace tag with the context name (e.g. CLIPBOARD_CONTENTS or with -1 suffix)
        return f"RESOURCE:{context_name}" 
    
    def display_string(self, suggestion: str) -> str:
        return "📋" + suggestion