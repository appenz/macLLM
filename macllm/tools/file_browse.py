import os
import time
from pathlib import Path

from smolagents import tool

from macllm.tags.file_tag import FileTag
from macllm.tools.file_utils import validate_indexed_path

_tool_call_counter = {"list_directory": 0, "view_directory_structure": 0}


def _status_manager():
    from macllm.macllm import MacLLM
    return MacLLM.get_status_manager()


@tool
def list_directory(path: str) -> str:
    """
    List all indexed files in a specific directory (non-recursive).

    Args:
        path: The directory path to list (must be within an indexed directory).

    Returns:
        A list of filenames in the directory, or an error description.
    """
    _tool_call_counter["list_directory"] += 1
    tool_id = f"list_directory_{_tool_call_counter['list_directory']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        status.fail_tool_call(tool_id, "Not in indexed dirs")
        return f"Error: Path '{path}' is not within an indexed directory."

    if not os.path.isdir(expanded):
        status.fail_tool_call(tool_id, "Not a directory")
        return f"Error: Not a directory: {expanded}"

    files = []
    for _basename, filepath in FileTag._index:
        if Path(filepath).parent == Path(expanded):
            files.append(Path(filepath).name)

    if not files:
        status.complete_tool_call(tool_id, "Empty")
        return f"No indexed files in: {expanded}"

    files.sort()
    status.complete_tool_call(tool_id, f"{len(files)} files")
    return f"Directory: {expanded}\n\n" + "\n".join(files)


@tool
def view_directory_structure() -> str:
    """
    Show the directory tree of all indexed directories and their files.

    Returns:
        A tree-style listing of all indexed directories and files.
    """
    _tool_call_counter["view_directory_structure"] += 1
    tool_id = f"view_directory_structure_{_tool_call_counter['view_directory_structure']}_{int(time.time() * 1000)}"
    status = _status_manager()

    if not FileTag._indexed_directories:
        status.complete_tool_call(tool_id, "No dirs")
        return "No directories are currently indexed."

    tree: dict[str, list[str]] = {}

    for _basename, filepath in FileTag._index:
        parent = str(Path(filepath).parent)
        if parent not in tree:
            tree[parent] = []
        tree[parent].append(Path(filepath).name)

    lines = []
    for root_dir in FileTag._indexed_directories:
        lines.append(f"{root_dir}/")
        _render_subtree(lines, root_dir, tree, indent=1)

    status.complete_tool_call(tool_id, f"{len(FileTag._index)} files")
    return "\n".join(lines)


def _render_subtree(lines: list[str], current_dir: str, tree: dict[str, list[str]], indent: int):
    """Recursively render directories and files as indented lines."""
    prefix = "  " * indent

    subdirs = sorted(
        d for d in tree if d != current_dir and d.startswith(current_dir + os.sep)
        and os.sep not in d[len(current_dir) + 1:]
    )

    for subdir in subdirs:
        dir_name = Path(subdir).name
        lines.append(f"{prefix}{dir_name}/")
        _render_subtree(lines, subdir, tree, indent + 1)

    if current_dir in tree:
        for filename in sorted(tree[current_dir]):
            lines.append(f"{prefix}{filename}")
