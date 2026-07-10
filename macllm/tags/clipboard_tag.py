from .base import TagPlugin


class ClipboardTag(TagPlugin):
    """Expands @clipboard into an instruction to call read_clipboard()."""

    def get_prefixes(self) -> list[str]:
        return ["@clipboard"]

    def expand(self, tag: str, conversation, request):
        return "Clipboard (use read_clipboard())"

    def display_string(self, suggestion: str) -> str:
        return "📋" + suggestion
