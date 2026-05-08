from .base import TagPlugin


class ToolTag(TagPlugin):
    def get_prefixes(self):
        return ["/notool"]

    def expand(self, tag, conversation, request):
        if tag == "/notool":
            request.no_tools = True
        return ""
