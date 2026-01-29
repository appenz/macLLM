import os
from pathlib import Path

from smolagents import tool

from macllm.tags.file_tag import FileTag


def _write_file(file_identifier: str, text: str, must_exist: bool) -> str:
    """Core implementation for file_append and file_create."""
    filepath = _resolve_file_path(file_identifier)
    if filepath is None:
        return f"Error: Cannot write to '{file_identifier}'. Must be a valid file ID, a filename for an indexed directory, or a path referenced in the conversation."

    file_exists = os.path.exists(filepath)

    if must_exist and not file_exists:
        return f"Error: File does not exist: {filepath}. Use file_create to create new files."
    if not must_exist and file_exists:
        return f"Error: File already exists: {filepath}. Use file_append to add content to existing files."

    try:
        parent = Path(filepath).parent
        if not parent.exists():
            return f"Error: Directory does not exist: {parent}"

        file_has_content = file_exists and os.path.getsize(filepath) > 0

        with open(filepath, "a", encoding="utf-8") as f:
            if file_has_content:
                f.write("\n")
            f.write(text)

        if not file_exists:
            FileTag._index.append((Path(filepath).name.lower(), filepath))
            FileTag._index.sort(key=lambda t: t[0])

        action = "appended to" if file_exists else "created"
        return f"Successfully {action}: {filepath}"

    except PermissionError:
        return f"Error: Permission denied writing to: {filepath}"
    except Exception as e:
        return f"Error writing to file: {e}"


@tool
def file_append(file_identifier: str, text: str) -> str:
    """
    Append text to an existing file.

    Args:
        file_identifier: Either a file ID from search_files (e.g., "42") or a path (e.g. "/User/foo/note.md").
        text: The text content to append to the file.

    Returns:
        Success message with the file path, or an error description.
    """
    return _write_file(file_identifier, text, must_exist=True)


@tool
def file_create(file_identifier: str, text: str) -> str:
    """
    Create a new file with the given content. Fails if the file already exists.

    Args:
        file_identifier: Either a file ID from search_files (e.g., "42") or a path (e.g. "/User/foo/note.md").
        text: The text content to write to the new file.

    Returns:
        Success message with the file path, or an error description.
    """
    return _write_file(file_identifier, text, must_exist=False)


def _resolve_file_path(file_identifier: str) -> str | None:
    """Resolve file_identifier to a valid file path."""
    if file_identifier.isdigit():
        file_id = int(file_identifier)
        if 0 <= file_id < len(FileTag._index):
            _, filepath = FileTag._index[file_id]
            return filepath
        return None

    if "/" not in file_identifier and "\\" not in file_identifier:
        if not FileTag._indexed_directories:
            return None
        if not file_identifier.lower().endswith(FileTag.EXTENSIONS):
            file_identifier += ".md"
        return os.path.join(FileTag._indexed_directories[0], file_identifier)

    expanded_path = os.path.expanduser(file_identifier)

    for indexed_dir in FileTag._indexed_directories:
        if expanded_path.startswith(indexed_dir + os.sep) or expanded_path == indexed_dir:
            if not os.path.exists(expanded_path) and not expanded_path.lower().endswith(FileTag.EXTENSIONS):
                expanded_path += ".md"
            return expanded_path

    if FileTag._macllm and FileTag._macllm.check_path_in_active_conversations(expanded_path):
        return expanded_path

    return None
