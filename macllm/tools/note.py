"""Semantic search over indexed filesystem mounts."""

from pathlib import Path

from macllm.core.virtual_filesystem import indexed_virtual_path
from macllm.tags.file_tag import FileTag
from macllm.tools._debug import macllm_tool, set_tool_message


@macllm_tool
def search_notes(query: str) -> str:
    """Search indexed notes using semantic similarity.

    Args:
        query: Query describing the notes to find.
    """
    set_tool_message(f'Searching notes for "{query}"')
    results = FileTag.search(query)
    output = []
    for _file_id, score, filepath, preview, truncated in results:
        virtual = indexed_virtual_path(filepath)
        if virtual is None:
            continue
        status = "(truncated)" if truncated else "(complete)"
        output.append(
            f"[{virtual}] {Path(filepath).name} {status}\n"
            f"Score: {score:.3f}\n{preview}\n"
        )
    return "\n---\n".join(output) if output else "No matching notes found"
