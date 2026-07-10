from urllib.parse import urlparse

from .base import TagPlugin

class URLTag(TagPlugin):
    """Expands @http://... or @https://... into a fetchable web page reference."""

    def get_prefixes(self):
        return ["@http://", "@https://"]

    def expand(self, tag: str, conversation, request):
        url = tag[1:]  # remove '@'
        try:
            ref = self._register_url(conversation, url)
        except Exception as e:
            if self.macllm.args.debug:
                self.macllm.debug_log(str(e), 2)
            return tag

        content = (
            f"Web page reference: {ref}\n"
            f"Use web_fetch(\"{ref}\") to retrieve the page text if needed."
        )
        context_name = conversation.add_context(
            "url",
            url,
            "url",
            content,
        )
        if request is not None:
            request.add_context_block(context_name, content)
            return f"context:{context_name}"
        return f"\n\n--- context:{context_name} ---\n{content}\n--- end context:{context_name} ---"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _register_url(self, conversation, url: str) -> str:
        result = urlparse(url)
        if result.scheme not in {"http", "https"} or not result.netloc:
            raise ValueError("Invalid URL format")
        return conversation.register_web_page(url)