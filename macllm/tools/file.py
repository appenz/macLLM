"""File tools: search, read, write, move, delete, and browse indexed files."""

import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from smolagents import tool

from macllm.tags.file_tag import FileTag

BACKUP_DIR = os.path.expanduser("~/.macllm-backup")

_tool_call_counter = {
    "file_append": 0,
    "file_create": 0,
    "file_modify": 0,
    "search_files": 0,
    "read_file": 0,
    "file_move": 0,
    "file_delete": 0,
    "list_directory": 0,
    "view_directory_structure": 0,
}


def validate_indexed_path(path: str) -> str | None:
    """Validate that *path* is inside an indexed directory.

    Expands ``~`` and resolves the path.  Returns the absolute path string
    if it falls within one of ``FileTag._indexed_directories``, otherwise
    ``None``.
    """
    expanded = os.path.abspath(os.path.expanduser(path))
    for indexed_dir in FileTag._indexed_directories:
        if expanded.startswith(indexed_dir + os.sep) or expanded == indexed_dir:
            return expanded
    return None


def backup_file(filepath: str) -> str:
    """Copy *filepath* into ``~/.macllm-backup/`` before a destructive operation.

    Backup file names follow the pattern ``YYYY-MM-DD-HH:MM <filename>``
    with ``-1``, ``-2``, … appended for collision avoidance.

    Returns the backup path on success.
    Raises ``OSError`` if the backup cannot be written.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)

    filename = Path(filepath).name
    timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M")
    base_name = f"{timestamp} {filename}"
    backup_path = os.path.join(BACKUP_DIR, base_name)

    counter = 0
    while os.path.exists(backup_path):
        counter += 1
        backup_path = os.path.join(BACKUP_DIR, f"{base_name}-{counter}")

    shutil.copy2(filepath, backup_path)
    return backup_path


def _status_manager():
    from macllm.macllm import MacLLM
    return MacLLM.get_status_manager()


# --- file_write tools ---


@tool
def file_append(path: str, text: str) -> str:
    """
    Append text to an existing file.

    Args:
        path: The file path (must be within an indexed directory).
        text: The text content to append to the file.

    Returns:
        Success message with the file path, or an error description.
    """
    _tool_call_counter["file_append"] += 1
    tool_id = f"file_append_{_tool_call_counter['file_append']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        status.fail_tool_call(tool_id, "Not in indexed dirs")
        return f"Error: Path '{path}' is not within an indexed directory."

    if not os.path.exists(expanded):
        status.fail_tool_call(tool_id, "File not found")
        return f"Error: File does not exist: {expanded}. Use file_create to create new files."

    try:
        has_content = os.path.getsize(expanded) > 0
        with open(expanded, "a", encoding="utf-8") as f:
            if has_content:
                f.write("\n")
            f.write(text)
        filename = Path(expanded).name
        status.complete_tool_call(tool_id, filename)
        return f"Successfully appended to: {expanded}"
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error writing to file: {e}"


@tool
def file_create(path: str, text: str) -> str:
    """
    Create a new file with the given content. Fails if the file already exists.

    Args:
        path: The file path (must be within an indexed directory). Extension .md is added if missing.
        text: The text content to write to the new file.

    Returns:
        Success message with the file path, or an error description.
    """
    _tool_call_counter["file_create"] += 1
    tool_id = f"file_create_{_tool_call_counter['file_create']}_{int(time.time() * 1000)}"
    status = _status_manager()

    if not path.lower().endswith(FileTag.EXTENSIONS):
        path = path + ".md"

    expanded = validate_indexed_path(path)
    if expanded is None:
        status.fail_tool_call(tool_id, "Not in indexed dirs")
        return f"Error: Path '{path}' is not within an indexed directory."

    if os.path.exists(expanded):
        status.fail_tool_call(tool_id, "File exists")
        return f"Error: File already exists: {expanded}. Use file_append to add content."

    parent = Path(expanded).parent
    if not parent.exists():
        status.fail_tool_call(tool_id, "Dir not found")
        return f"Error: Directory does not exist: {parent}"

    try:
        with open(expanded, "w", encoding="utf-8") as f:
            f.write(text)
        FileTag._index.append((Path(expanded).name.lower(), expanded))
        FileTag._index.sort(key=lambda t: t[0])
        filename = Path(expanded).name
        status.complete_tool_call(tool_id, filename)
        return f"Successfully created: {expanded}"
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error creating file: {e}"


@tool
def file_modify(path: str, new_content: str) -> str:
    """
    Replace the entire content of an existing file. A backup of the original is saved automatically.

    Args:
        path: The file path (must be within an indexed directory).
        new_content: The new content that will replace the file's current content.

    Returns:
        Success message with the file path and backup location, or an error description.
    """
    _tool_call_counter["file_modify"] += 1
    tool_id = f"file_modify_{_tool_call_counter['file_modify']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        status.fail_tool_call(tool_id, "Not in indexed dirs")
        return f"Error: Path '{path}' is not within an indexed directory."

    if not os.path.exists(expanded):
        status.fail_tool_call(tool_id, "File not found")
        return f"Error: File does not exist: {expanded}."

    try:
        backup_path = backup_file(expanded)
    except OSError as e:
        status.fail_tool_call(tool_id, "Backup failed")
        return f"Error: Could not create backup: {e}"

    try:
        with open(expanded, "w", encoding="utf-8") as f:
            f.write(new_content)
        filename = Path(expanded).name
        status.complete_tool_call(tool_id, filename)
        return f"Successfully modified: {expanded}\nBackup saved to: {backup_path}"
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error modifying file: {e}"


# --- file_search tools ---


@tool
def search_files(query: str) -> str:
    """
    Search indexed files using semantic similarity.

    Args:
        query: The search query to find relevant notes or personal files.

    Returns:
        Top 5 matching files with path, filename, relevance score, and first 1000 characters of content.
    """
    _tool_call_counter["search_files"] += 1
    tool_id = f"search_files_{_tool_call_counter['search_files']}_{int(time.time() * 1000)}"
    status = _status_manager()
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
    _tool_call_counter["read_file"] += 1
    tool_id = f"read_file_{_tool_call_counter['read_file']}_{int(time.time() * 1000)}"
    status = _status_manager()

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


# --- file_ops tools ---


@tool
def file_move(source_path: str, dest_path: str) -> str:
    """
    Move or rename a file within indexed directories. Fails if the destination already exists.

    Args:
        source_path: The current file path (must exist, must be in an indexed directory).
        dest_path: The new file path (must be in an indexed directory, must not already exist).

    Returns:
        Success message, or an error description.
    """
    _tool_call_counter["file_move"] += 1
    tool_id = f"file_move_{_tool_call_counter['file_move']}_{int(time.time() * 1000)}"
    status = _status_manager()

    src = validate_indexed_path(source_path)
    if src is None:
        status.fail_tool_call(tool_id, "Source not in indexed dirs")
        return f"Error: Source path '{source_path}' is not within an indexed directory."

    if not os.path.exists(src):
        status.fail_tool_call(tool_id, "Source not found")
        return f"Error: Source file does not exist: {src}"

    dst = validate_indexed_path(dest_path)
    if dst is None:
        status.fail_tool_call(tool_id, "Dest not in indexed dirs")
        return f"Error: Destination path '{dest_path}' is not within an indexed directory."

    if os.path.exists(dst):
        status.fail_tool_call(tool_id, "Dest exists")
        return f"Error: Destination already exists: {dst}. Will not overwrite."

    dst_parent = Path(dst).parent
    if not dst_parent.exists():
        status.fail_tool_call(tool_id, "Dest dir not found")
        return f"Error: Destination directory does not exist: {dst_parent}"

    try:
        shutil.move(src, dst)

        FileTag._index = [
            (name, fp) for name, fp in FileTag._index if fp != src
        ]
        FileTag._index.append((Path(dst).name.lower(), dst))
        FileTag._index.sort(key=lambda t: t[0])

        src_name = Path(src).name
        dst_name = Path(dst).name
        status.complete_tool_call(tool_id, f"{src_name} -> {dst_name}")
        return f"Successfully moved: {src} -> {dst}"
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error moving file: {e}"


@tool
def file_delete(path: str) -> str:
    """
    Delete a file. A backup is saved automatically before deletion.

    Args:
        path: The file path to delete (must be within an indexed directory).

    Returns:
        Success message with the backup location, or an error description.
    """
    _tool_call_counter["file_delete"] += 1
    tool_id = f"file_delete_{_tool_call_counter['file_delete']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        status.fail_tool_call(tool_id, "Not in indexed dirs")
        return f"Error: Path '{path}' is not within an indexed directory."

    if not os.path.exists(expanded):
        status.fail_tool_call(tool_id, "File not found")
        return f"Error: File does not exist: {expanded}"

    try:
        backup_path = backup_file(expanded)
    except OSError as e:
        status.fail_tool_call(tool_id, "Backup failed")
        return f"Error: Could not create backup before deletion: {e}"

    try:
        os.remove(expanded)

        FileTag._index = [
            (name, fp) for name, fp in FileTag._index if fp != expanded
        ]

        filename = Path(expanded).name
        status.complete_tool_call(tool_id, filename)
        return f"Successfully deleted: {expanded}\nBackup saved to: {backup_path}"
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error deleting file: {e}"


# --- file_browse tools ---


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
