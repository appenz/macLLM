import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import requests
from smolagents import tool

# Use a mutable container to avoid Python global variable binding issues
_state = {"search_count": 0, "tool_call_counter": 0}
MAX_SEARCHES_PER_RUN = 50
MAX_PARALLEL_SEARCHES = 5

BRAVE_API_URL = "https://api.search.brave.com/res/v1/web/search"


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


def _format_results(search_results: list[dict]) -> str:
    """Format search results into a readable string with just the content."""
    output = []
    
    for item in search_results:
        query = item["query"]
        results = item["results"]
        
        output.append(f"## {query}\n")
        
        web_results = results.get("web", {}).get("results", [])
        if not web_results:
            output.append("No results found.\n")
            continue
        
        # Only include the description/content snippets - the agent just needs the facts
        for result in web_results[:5]:  # Limit to top 5 results per query
            description = result.get("description", "")
            if description:
                output.append(f"- {description}")
        
        output.append("")
    
    return "\n".join(output)


@tool
def web_search(queries: list[str]) -> str:
    """
    Search the web using Brave Search API.
    
    Args:
        queries: List of search queries to execute. Maximum 50 searches per agent run.
    
    Returns:
        Search results with relevant content snippets from each result.
    """
    from macllm.macllm import MacLLM
    
    # Generate unique tool call ID and register start
    _state["tool_call_counter"] += 1
    tool_id = f"web_search_{_state['tool_call_counter']}_{int(time.time() * 1000)}"
    status = MacLLM.get_status_manager()
    status.start_tool_call(tool_id, "web_search", {"queries": queries})
    
    try:
        api_key = os.getenv("BRAVE_API_KEY")
        if not api_key:
            raise ValueError("BRAVE_API_KEY environment variable is not set")
        
        if not queries:
            status.complete_tool_call(tool_id, "No queries")
            return "No queries provided."
        
        # Check if we would exceed the limit
        current_count = _state["search_count"]
        if current_count + len(queries) > MAX_SEARCHES_PER_RUN:
            error_msg = f"Limit exceeded: {current_count}/{MAX_SEARCHES_PER_RUN}"
            status.fail_tool_call(tool_id, error_msg)
            raise ValueError(
                f"Search limit exceeded: already performed {current_count} searches, "
                f"requesting {len(queries)} more, but maximum is {MAX_SEARCHES_PER_RUN} per agent run"
            )
        
        # Execute searches in parallel with max 5 concurrent
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
        
        # Update the counter after successful execution
        _state["search_count"] += len(queries)
        
        # Sort results by original query order
        query_order = {q: i for i, q in enumerate(queries)}
        results.sort(key=lambda x: query_order.get(x["query"], len(queries)))
        
        status.complete_tool_call(tool_id, f"{len(queries)} queries done")
        return _format_results(results)
        
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise
