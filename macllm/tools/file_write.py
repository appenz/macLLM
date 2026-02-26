import os
import time
from pathlib import Path

from smolagents import tool

from macllm.tags.file_tag import FileTag
from macllm.tools.file_utils import validate_indexed_path, backup_file

_tool_call_counter = {"file_append": 0, "file_create": 0, "file_modify": 0}


def _status_manager():
    from macllm.macllm import MacLLM
    return MacLLM.get_status_manager()


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
