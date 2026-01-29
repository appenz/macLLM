import time
from pathlib import Path

from smolagents import tool

from macllm.tags.file_tag import FileTag

_tool_call_counter = {"search_files": 0, "read_full_file": 0}


@tool
def search_files(query: str) -> str:
    """
    Search indexed files using semantic similarity.

    Args:
        query: The search query to find relevant notes or personal files.

    Returns:
        Top 5 matching files with file ID, filename, and first 1000 characters of content.
    """
    from macllm.macllm import MacLLM
    
    # Register start (search can take a moment)
    _tool_call_counter["search_files"] += 1
    tool_id = f"search_files_{_tool_call_counter['search_files']}_{int(time.time() * 1000)}"
    status = MacLLM.get_status_manager()
    status.start_tool_call(tool_id, "search_files", {"query": query})
    
    try:
        results = FileTag.search(query)
        if not results:
            status.complete_tool_call(tool_id, "No matches")
            return "No matching files found"

        output_parts = []
        for file_id, score, filepath, preview, truncated in results:
            filename = Path(filepath).name
            file_status = "(truncated)" if truncated else "(complete)"
            output_parts.append(f"[File ID: {file_id}] {filename} {file_status}\nScore: {score:.3f}\n{preview}\n")

        status.complete_tool_call(tool_id, f"{len(results)} files found")
        return "\n---\n".join(output_parts)
        
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
def read_full_file(file_id: int) -> str:
    """
    Read the full content of an indexed file by its ID.

    Args:
        file_id: The file ID returned by search_files.

    Returns:
        The full content of the file (up to 10,000 characters).
    """
    from macllm.macllm import MacLLM
    
    _tool_call_counter["read_full_file"] += 1
    tool_id = f"read_full_file_{_tool_call_counter['read_full_file']}_{int(time.time() * 1000)}"
    status = MacLLM.get_status_manager()
    
    try:
        content, filepath = FileTag.get_file_content(file_id)
        filename = Path(filepath).name
        status.complete_tool_call(tool_id, filename)
        return f"File: {filename}\n\n{content}"
    except IndexError as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        return f"Error: {e}"
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        return f"Error reading file: {e}"
