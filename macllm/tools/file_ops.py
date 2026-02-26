import os
import shutil
import time
from pathlib import Path

from smolagents import tool

from macllm.tags.file_tag import FileTag
from macllm.tools.file_utils import validate_indexed_path, backup_file

_tool_call_counter = {"file_move": 0, "file_delete": 0}


def _status_manager():
    from macllm.macllm import MacLLM
    return MacLLM.get_status_manager()


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
