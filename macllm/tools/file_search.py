import time
from pathlib import Path

from smolagents import tool

from macllm.tags.file_tag import FileTag
from macllm.tools.file_utils import validate_indexed_path

_tool_call_counter = {"search_files": 0, "read_file": 0}


@tool
def search_files(query: str) -> str:
    """
    Search indexed files using semantic similarity.

    Args:
        query: The search query to find relevant notes or personal files.

    Returns:
        Top 5 matching files with path, filename, relevance score, and first 1000 characters of content.
    """
    from macllm.macllm import MacLLM

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
        for _file_id, score, filepath, preview, truncated in results:
            filename = Path(filepath).name
            file_status = "(truncated)" if truncated else "(complete)"
            output_parts.append(
                f"[{filepath}] {filename} {file_status}\n"
                f"Score: {score:.3f}\n{preview}\n"
            )

        status.complete_tool_call(tool_id, f"{len(results)} files found")
        return "\n---\n".join(output_parts)

    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
def read_file(path: str) -> str:
    """
    Read the full content of a file by its path.

    Args:
        path: The file path (as returned by search_files).

    Returns:
        The full content of the file (up to 10,000 characters).
    """
    from macllm.macllm import MacLLM

    _tool_call_counter["read_file"] += 1
    tool_id = f"read_file_{_tool_call_counter['read_file']}_{int(time.time() * 1000)}"
    status = MacLLM.get_status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        status.fail_tool_call(tool_id, "Not in indexed dirs")
        return f"Error: Path '{path}' is not within an indexed directory."

    if not Path(expanded).is_file():
        status.fail_tool_call(tool_id, "File not found")
        return f"Error: File not found: {expanded}"

    try:
        with open(expanded, "r", encoding="utf-8") as f:
            content = f.read(FileTag.MAX_FULL_FILE_LEN)
        filename = Path(expanded).name
        status.complete_tool_call(tool_id, filename)
        return f"File: {filename}\n\n{content}"
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        return f"Error reading file: {e}"
