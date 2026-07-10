from urllib.parse import urlparse

from .base import TagPlugin


class URLTag(TagPlugin):
    """Expands @http://... or @https://... into a web_fetch instruction."""

    def get_prefixes(self):
        return ["@http://", "@https://"]

    def expand(self, tag: str, conversation, request):
        url = tag[1:]
        try:
            result = urlparse(url)
            if result.scheme not in {"http", "https"} or not result.netloc:
                raise ValueError("Invalid URL format")
        except Exception as e:
            if self.macllm.args.debug:
                self.macllm.debug_log(str(e), 2)
            return tag

        return f'{url} (use web_fetch("{url}") to read the page)'
