
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests

from macllm.core.chat_history import add_source
from macllm.core.config import get_runtime_config
from macllm.tools._debug import macllm_tool, set_tool_message

_state = {"search_count": 0}
MAX_SEARCHES_PER_RUN = 50
WEB_FETCH_CHARS = 10_000
WEB_PAGE_MAX_CHARS = 100_000

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"
WEB_USER_AGENT = "Mozilla/5.0"


def reset_search_counter():
    """Reset the search counter. Call this before each agent run."""
    _state["search_count"] = 0


def _search_single_query(query: str, api_key: str) -> dict:
    """Execute a single search query against Brave API."""
    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": api_key,
    }
    params = {"q": query}
    
    response = requests.get(BRAVE_API_URL, headers=headers, params=params)
    response.raise_for_status()
    return response.json()


def _extract_page_text(html: str) -> str:
    """Extract readable text from an HTML document."""
    soup = BeautifulSoup(html, "html.parser")
    for element in soup(["script", "style", "header", "footer", "nav"]):
        element.decompose()

    text = soup.get_text(separator="\n")
    lines = (line.strip() for line in text.splitlines())
    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
    return "\n".join(chunk for chunk in chunks if chunk)


def _retrieve_url_text(url: str) -> tuple[str, bool]:
    """Fetch *url* and return cleaned text plus whether it hit the page cap."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("Invalid URL format")

    response = requests.get(url, headers={"User-Agent": WEB_USER_AGENT}, timeout=30)
    response.raise_for_status()

    text = _extract_page_text(response.text)
    truncated = len(text) > WEB_PAGE_MAX_CHARS
    return text[:WEB_PAGE_MAX_CHARS], truncated


def _format_results(results: dict) -> str:
    """Format search results with their real URLs."""
    output = []
    for result in results.get("web", {}).get("results", [])[:5]:
        url = result.get("url", "")
        title = result.get("title", "")
        description = result.get("description", "")
        parts = [part for part in (url or title, title if url else "", description) if part]
        if parts:
            output.append("- " + " — ".join(parts))
    return "\n".join(output)


@macllm_tool
def web_search(query: str) -> str:
    """
    Search the web for one query using Brave Search API.
    
    Args:
        query: One search query. Maximum 50 searches per agent run.
    
    Returns:
        Search results with relevant content snippets from each result.
    """
    if not isinstance(query, str):
        raise ValueError("query must be a single string")
    query = query.strip()
    if not query:
        return "No query provided."
    if _state["search_count"] >= MAX_SEARCHES_PER_RUN:
        raise ValueError(
            f"Search limit exceeded: maximum is {MAX_SEARCHES_PER_RUN} per agent run"
        )

    api_key = get_runtime_config().api_keys.brave
    if not api_key:
        raise ValueError("brave API key is not configured in config.toml")

    set_tool_message(f'Searching the web for "{query}"')
    try:
        results = _search_single_query(query, api_key)
    except Exception:
        results = {}
    _state["search_count"] += 1
    return _format_results(results) or "No results found."


@macllm_tool
def web_fetch(url: str, start: int = 0) -> str:
    """
    Fetch readable text for a URL.

    Args:
        url: A real http(s) URL.
        start: Zero-based character offset for fetching the next chunk.

    Returns:
        Up to 10,000 characters of cleaned page text. If more text is available,
        the result begins with a compact truncation line showing the returned range.
    """
    url = (url or "").strip()
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return f"Error: Invalid URL: {url}"

    try:
        start = int(start)
    except (TypeError, ValueError):
        return f"Error: start must be an integer offset, got {start!r}."
    if start < 0:
        return "Error: start must be >= 0."

    set_tool_message(f"Fetching {url}")
    try:
        content, truncated = _retrieve_url_text(url)
    except Exception as exc:
        return f"Error fetching {url}: {exc}"

    total = len(content)
    if start >= total:
        return f"Error: start {start} is beyond available content length {total}."

    end = min(start + WEB_FETCH_CHARS, total)
    chunk = content[start:end]
    has_more = end < total or truncated

    # Direct fetch adds a Source (search results alone do not).
    add_source("web", url)

    if has_more:
        return f"[page truncated, chars {start}-{end} of {total}]\n\n{chunk}"
    return chunk
