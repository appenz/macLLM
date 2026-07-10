
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests

from macllm.core.chat_history import add_source
from macllm.core.config import get_runtime_config
from macllm.tools._debug import macllm_tool, set_tool_message

_state = {"search_count": 0}
MAX_SEARCHES_PER_RUN = 50
MAX_PARALLEL_SEARCHES = 5
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
    return {"query": query, "results": response.json()}


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


def _format_results(search_results: list[dict]) -> str:
    """Format search results with their real URLs."""
    output = []
    
    for item in search_results:
        query = item["query"]
        results = item["results"]
        
        output.append(f"## {query}\n")
        
        web_results = results.get("web", {}).get("results", [])
        if not web_results:
            output.append("No results found.\n")
            continue
        
        for result in web_results[:5]:
            url = result.get("url", "")
            title = result.get("title", "")
            description = result.get("description", "")
            label_parts = []
            if url:
                label_parts.append(url)
            elif title:
                label_parts.append(title)

            if title and (not label_parts or label_parts[-1] != title):
                label_parts.append(title)
            if description:
                label_parts.append(description)
            if label_parts:
                output.append("- " + " — ".join(label_parts))
        
        output.append("")
    
    return "\n".join(output)


@macllm_tool
def web_search(queries: list[str]) -> str:
    """
    Search the web using Brave Search API.
    
    Args:
        queries: List of search queries to execute. Maximum 50 searches per agent run.
    
    Returns:
        Search results with relevant content snippets from each result.
    """
    cfg = get_runtime_config()
    api_key = cfg.api_keys.brave
    if not api_key:
        raise ValueError(
            "brave API key is not configured in config.toml"
        )
    
    if not queries:
        return "No queries provided."

    shown = [f'"{q}"' for q in queries[:3]]
    if len(queries) > 3:
        shown.append("…")
    set_tool_message("Searching the web for " + ", ".join(shown))

    current_count = _state["search_count"]
    if current_count + len(queries) > MAX_SEARCHES_PER_RUN:
        raise ValueError(
            f"Search limit exceeded: already performed {current_count} searches, "
            f"requesting {len(queries)} more, but maximum is {MAX_SEARCHES_PER_RUN} per agent run"
        )
    
    results = []
    with ThreadPoolExecutor(max_workers=MAX_PARALLEL_SEARCHES) as executor:
        future_to_query = {
            executor.submit(_search_single_query, query, api_key): query
            for query in queries
        }
        
        for future in as_completed(future_to_query):
            query = future_to_query[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                results.append({"query": query, "results": {"error": str(e)}})
    
    _state["search_count"] += len(queries)
    
    query_order = {q: i for i, q in enumerate(queries)}
    results.sort(key=lambda x: query_order.get(x["query"], len(queries)))
    
    return _format_results(results)


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
