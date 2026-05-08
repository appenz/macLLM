"""Tag plugin for /quit and /exit commands — terminate the application."""

from macllm.tags.base import TagPlugin


class QuitTag(TagPlugin):

    def get_prefixes(self):
        return ["/quit", "/exit"]

    def expand(self, tag, conversation, request):
        from Cocoa import NSApp
        NSApp().terminate_(None)
        request.expanded_prompt = ""
        return ""
