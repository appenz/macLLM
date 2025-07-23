import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from .base import TagPlugin

class URLTag(TagPlugin):
    """Expands @http://... or @https://... by fetching page text and adding it as context."""

    def get_prefixes(self):
        return ["@http://", "@https://"]

    def expand(self, tag: str, conversation):
        url = tag[1:]  # remove '@'
        try:
            content = self._retrieve_url(url)
        except Exception as e:
            if self.macllm.debug:
                self.macllm.debug_log(str(e), 2)
            return tag

        context_name = conversation.add_context(
            "url",
            url,
            "url",
            content,
        )
        return f"content:{context_name}"

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _retrieve_url(self, url: str) -> str:
        # Basic url validation
        result = urlparse(url)
        if not all([result.scheme, result.netloc]):
            raise ValueError("Invalid URL format")

        response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')
        for element in soup(['script', 'style', 'header', 'footer', 'nav']):
            element.decompose()

        text = soup.get_text(separator='\n')
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        return '\n'.join(chunk for chunk in chunks if chunk) 