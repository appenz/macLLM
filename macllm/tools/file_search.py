from smolagents import tool

from macllm.tags.file_tag import FileTag


@tool
def search_files(query: str) -> str:
    """
    Search indexed files using semantic similarity.

    Args:
        query: The search query to find relevant files.

    Returns:
        Top 5 matching files with file ID, path, and first 1000 characters of content.
    """
    results = FileTag.search(query)
    if not results:
        return "No matching files found"

    output_parts = []
    for file_id, score, filepath, preview, truncated in results:
        status = "(truncated)" if truncated else "(complete)"
        output_parts.append(f"[File ID: {file_id}] {filepath} {status}\nScore: {score:.3f}\n{preview}\n")

    return "\n---\n".join(output_parts)


@tool
def read_full_file(file_id: int) -> str:
    """
    Read the full content of an indexed file by its ID.

    Args:
        file_id: The file ID returned by search_files.

    Returns:
        The full content of the file (up to 10,000 characters).
    """
    try:
        content, filepath = FileTag.get_file_content(file_id)
        return f"File: {filepath}\n\n{content}"
    except IndexError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error reading file: {e}"
