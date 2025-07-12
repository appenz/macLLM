from .base import ShortcutPlugin

class ClipboardPlugin(ShortcutPlugin):
    def __init__(self, ui):
        self.ui = ui
    
    def get_prefixes(self) -> list[str]:
        return ["@clipboard"]
    
    def expand(self, word: str, request) -> None:
        content = self.ui.read_clipboard()
        request.expanded_prompt = request.expanded_prompt.replace(word, " CLIPBOARD_CONTENTS ")
        request.context += f"\n--- CLIPBOARD_CONTENTS START ---\n{content}\n--- CLIPBOARD_CONTENTS END ---\n\n" 