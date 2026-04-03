"""Note tools: search, read, write, move, delete, browse, and manage folders for indexed notes."""

import os
import shutil
import time
from datetime import datetime
from pathlib import Path

from smolagents import tool

from macllm.tags.file_tag import FileTag

BACKUP_DIR = os.path.expanduser("~/.macllm-backup")

_tool_call_counter = {
    "note_append": 0,
    "note_create": 0,
    "note_modify": 0,
    "search_notes": 0,
    "read_note": 0,
    "note_move": 0,
    "note_delete": 0,
    "list_folder": 0,
    "view_folder_structure": 0,
    "folder_create": 0,
    "folder_delete": 0,
}


def validate_indexed_path(path: str) -> str | None:
    """Validate that *path* is inside an indexed folder.

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


def backup_folder(folderpath: str) -> str:
    """Copy *folderpath* (entire tree) into ``~/.macllm-backup/`` before a destructive operation.

    Backup directory names follow the pattern ``YYYY-MM-DD-HH:MM <foldername>``
    with ``-1``, ``-2``, … appended for collision avoidance.

    Returns the backup path on success.
    Raises ``OSError`` if the backup cannot be written.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)

    foldername = Path(folderpath).name
    timestamp = datetime.now().strftime("%Y-%m-%d-%H:%M")
    base_name = f"{timestamp} {foldername}"
    backup_path = os.path.join(BACKUP_DIR, base_name)

    counter = 0
    while os.path.exists(backup_path):
        counter += 1
        backup_path = os.path.join(BACKUP_DIR, f"{base_name}-{counter}")

    shutil.copytree(folderpath, backup_path)
    return backup_path


def _status_manager():
    from macllm.macllm import MacLLM
    return MacLLM.get_status_manager()


def _debug_log(message: str, level: int = 0) -> None:
    from macllm.macllm import MacLLM

    app = MacLLM._instance
    if app is not None:
        app.debug_log(message, level)


# --- note write tools ---


@tool
def note_append(path: str, text: str) -> str:
    """
    Append text to an existing note.

    Args:
        path: The note path (must be within an indexed folder).
        text: The text content to append to the note.

    Returns:
        Success message with the note path, or an error description.
    """
    _tool_call_counter["note_append"] += 1
    tool_id = f"note_append_{_tool_call_counter['note_append']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"note_append: path not indexed – {path}", 2)
        status.fail_tool_call(tool_id, "Not in indexed folders")
        return f"Error: Path '{path}' is not within an indexed folder."

    if not os.path.exists(expanded):
        _debug_log(f"note_append: not found – {expanded}", 2)
        status.fail_tool_call(tool_id, "Note not found")
        return f"Error: Note does not exist: {expanded}. Use note_create to create new notes."

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
        _debug_log(f"note_append: write failed – {e}", 2)
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error writing to note: {e}"


@tool
def note_create(path: str, text: str) -> str:
    """
    Create a new note with the given content. Fails if the note already exists.

    Args:
        path: The note path (must be within an indexed folder). Extension .md is added if missing.
        text: The text content to write to the new note.

    Returns:
        Success message with the note path, or an error description.
    """
    _tool_call_counter["note_create"] += 1
    tool_id = f"note_create_{_tool_call_counter['note_create']}_{int(time.time() * 1000)}"
    status = _status_manager()

    if not path.lower().endswith(FileTag.EXTENSIONS):
        path = path + ".md"

    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"note_create: path not indexed – {path}", 2)
        status.fail_tool_call(tool_id, "Not in indexed folders")
        return f"Error: Path '{path}' is not within an indexed folder."

    if os.path.exists(expanded):
        _debug_log(f"note_create: already exists – {expanded}", 2)
        status.fail_tool_call(tool_id, "Note exists")
        return f"Error: Note already exists: {expanded}. Use note_append to add content."

    parent = Path(expanded).parent
    if not parent.exists():
        _debug_log(f"note_create: folder not found – {parent}", 2)
        status.fail_tool_call(tool_id, "Folder not found")
        return f"Error: Folder does not exist: {parent}"

    try:
        with open(expanded, "w", encoding="utf-8") as f:
            f.write(text)
        FileTag._index.append((Path(expanded).name.lower(), expanded))
        FileTag._index.sort(key=lambda t: t[0])
        filename = Path(expanded).name
        status.complete_tool_call(tool_id, filename)
        return f"Successfully created: {expanded}"
    except Exception as e:
        _debug_log(f"note_create: failed – {e}", 2)
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error creating note: {e}"


@tool
def note_modify(path: str, new_content: str) -> str:
    """
    Replace the entire content of an existing note. A backup of the original is saved automatically.

    Args:
        path: The note path (must be within an indexed folder).
        new_content: The new content that will replace the note's current content.

    Returns:
        Success message with the note path and backup location, or an error description.
    """
    _tool_call_counter["note_modify"] += 1
    tool_id = f"note_modify_{_tool_call_counter['note_modify']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"note_modify: path not indexed – {path}", 2)
        status.fail_tool_call(tool_id, "Not in indexed folders")
        return f"Error: Path '{path}' is not within an indexed folder."

    if not os.path.exists(expanded):
        _debug_log(f"note_modify: not found – {expanded}", 2)
        status.fail_tool_call(tool_id, "Note not found")
        return f"Error: Note does not exist: {expanded}."

    try:
        backup_path = backup_file(expanded)
    except OSError as e:
        _debug_log(f"note_modify: backup failed – {e}", 2)
        status.fail_tool_call(tool_id, "Backup failed")
        return f"Error: Could not create backup: {e}"

    try:
        with open(expanded, "w", encoding="utf-8") as f:
            f.write(new_content)
        filename = Path(expanded).name
        status.complete_tool_call(tool_id, filename)
        return f"Successfully modified: {expanded}\nBackup saved to: {backup_path}"
    except Exception as e:
        _debug_log(f"note_modify: write failed – {e}", 2)
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error modifying note: {e}"


# --- note search tools ---


@tool
def search_notes(query: str) -> str:
    """
    Search indexed notes using semantic similarity.

    Args:
        query: The search query to find relevant notes.

    Returns:
        Top 5 matching notes with path, filename, relevance score, and first 1000 characters of content.
    """
    _tool_call_counter["search_notes"] += 1
    tool_id = f"search_notes_{_tool_call_counter['search_notes']}_{int(time.time() * 1000)}"
    status = _status_manager()
    status.start_tool_call(tool_id, "search_notes", {"query": query})

    try:
        results = FileTag.search(query)
        if not results:
            status.complete_tool_call(tool_id, "No matches")
            return "No matching notes found"

        output_parts = []
        for _file_id, score, filepath, preview, truncated in results:
            filename = Path(filepath).name
            note_status = "(truncated)" if truncated else "(complete)"
            output_parts.append(
                f"[{filepath}] {filename} {note_status}\n"
                f"Score: {score:.3f}\n{preview}\n"
            )

        status.complete_tool_call(tool_id, f"{len(results)} notes found")
        return "\n---\n".join(output_parts)

    except Exception as e:
        _debug_log(f"search_notes: failed – {e}", 2)
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
def read_note(path: str) -> str:
    """
    Read the full content of a note by its path.

    Args:
        path: The note path (as returned by search_notes).

    Returns:
        The full content of the note (up to 10,000 characters).
    """
    _tool_call_counter["read_note"] += 1
    tool_id = f"read_note_{_tool_call_counter['read_note']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"read_note: path not indexed – {path}", 2)
        status.fail_tool_call(tool_id, "Not in indexed folders")
        return f"Error: Path '{path}' is not within an indexed folder."

    if not Path(expanded).is_file():
        _debug_log(f"read_note: not found – {expanded}", 2)
        status.fail_tool_call(tool_id, "Note not found")
        return f"Error: Note not found: {expanded}"

    try:
        with open(expanded, "r", encoding="utf-8") as f:
            content = f.read(FileTag.MAX_FULL_FILE_LEN)
        filename = Path(expanded).name
        status.complete_tool_call(tool_id, filename)
        return f"Note: {filename}\n\n{content}"
    except Exception as e:
        _debug_log(f"read_note: failed – {e}", 2)
        status.fail_tool_call(tool_id, str(e)[:50])
        return f"Error reading note: {e}"


# --- note ops tools ---


@tool
def note_move(source_path: str, dest_path: str) -> str:
    """
    Move or rename a note within indexed folders. Fails if the destination already exists.

    Args:
        source_path: The current note path (must exist, must be in an indexed folder).
        dest_path: The new note path (must be in an indexed folder, must not already exist).

    Returns:
        Success message, or an error description.
    """
    _tool_call_counter["note_move"] += 1
    tool_id = f"note_move_{_tool_call_counter['note_move']}_{int(time.time() * 1000)}"
    status = _status_manager()

    src = validate_indexed_path(source_path)
    if src is None:
        _debug_log(f"note_move: source not indexed – {source_path}", 2)
        status.fail_tool_call(tool_id, "Source not in indexed folders")
        return f"Error: Source path '{source_path}' is not within an indexed folder."

    if not os.path.exists(src):
        _debug_log(f"note_move: source not found – {src}", 2)
        status.fail_tool_call(tool_id, "Source not found")
        return f"Error: Source note does not exist: {src}"

    dst = validate_indexed_path(dest_path)
    if dst is None:
        _debug_log(f"note_move: dest not indexed – {dest_path}", 2)
        status.fail_tool_call(tool_id, "Dest not in indexed folders")
        return f"Error: Destination path '{dest_path}' is not within an indexed folder."

    if os.path.exists(dst):
        _debug_log(f"note_move: dest exists – {dst}", 2)
        status.fail_tool_call(tool_id, "Dest exists")
        return f"Error: Destination already exists: {dst}. Will not overwrite."

    dst_parent = Path(dst).parent
    if not dst_parent.exists():
        _debug_log(f"note_move: dest folder not found – {dst_parent}", 2)
        status.fail_tool_call(tool_id, "Dest folder not found")
        return f"Error: Destination folder does not exist: {dst_parent}"

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
        _debug_log(f"note_move: failed – {e}", 2)
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error moving note: {e}"


@tool
def note_delete(path: str) -> str:
    """
    Delete a note. A backup is saved automatically before deletion.

    Args:
        path: The note path to delete (must be within an indexed folder).

    Returns:
        Success message with the backup location, or an error description.
    """
    _tool_call_counter["note_delete"] += 1
    tool_id = f"note_delete_{_tool_call_counter['note_delete']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"note_delete: path not indexed – {path}", 2)
        status.fail_tool_call(tool_id, "Not in indexed folders")
        return f"Error: Path '{path}' is not within an indexed folder."

    if not os.path.exists(expanded):
        _debug_log(f"note_delete: not found – {expanded}", 2)
        status.fail_tool_call(tool_id, "Note not found")
        return f"Error: Note does not exist: {expanded}"

    try:
        backup_path = backup_file(expanded)
    except OSError as e:
        _debug_log(f"note_delete: backup failed – {e}", 2)
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
        _debug_log(f"note_delete: failed – {e}", 2)
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error deleting note: {e}"


# --- folder tools ---


@tool
def folder_create(path: str) -> str:
    """
    Create a new empty folder inside an indexed directory. The parent folder must already exist.

    Args:
        path: The folder path (must be within an indexed folder).

    Returns:
        Success message with the folder path, or an error description.
    """
    _tool_call_counter["folder_create"] += 1
    tool_id = f"folder_create_{_tool_call_counter['folder_create']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"folder_create: path not indexed – {path}", 2)
        status.fail_tool_call(tool_id, "Not in indexed folders")
        return f"Error: Path '{path}' is not within an indexed folder."

    if os.path.exists(expanded):
        if os.path.isdir(expanded):
            _debug_log(f"folder_create: already exists – {expanded}", 2)
            status.fail_tool_call(tool_id, "Folder exists")
            return f"Error: Folder already exists: {expanded}"
        _debug_log(f"folder_create: path is a file – {expanded}", 2)
        status.fail_tool_call(tool_id, "Path exists as file")
        return f"Error: Path exists but is not a folder: {expanded}"

    parent = Path(expanded).parent
    if not parent.exists():
        _debug_log(f"folder_create: parent not found – {parent}", 2)
        status.fail_tool_call(tool_id, "Parent not found")
        return f"Error: Parent folder does not exist: {parent}"

    try:
        os.mkdir(expanded)
        dir_name = Path(expanded).name
        status.complete_tool_call(tool_id, dir_name)
        return f"Successfully created folder: {expanded}"
    except Exception as e:
        _debug_log(f"folder_create: failed – {e}", 2)
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error creating folder: {e}"


@tool
def folder_delete(path: str) -> str:
    """
    Delete a folder and all of its contents. A backup of the entire folder tree is saved first.

    Cannot delete a root indexed folder (only subfolders within it).

    Args:
        path: The folder path to delete (must be within an indexed folder, not the indexed root).

    Returns:
        Success message with the backup location, or an error description.
    """
    _tool_call_counter["folder_delete"] += 1
    tool_id = f"folder_delete_{_tool_call_counter['folder_delete']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"folder_delete: path not indexed – {path}", 2)
        status.fail_tool_call(tool_id, "Not in indexed folders")
        return f"Error: Path '{path}' is not within an indexed folder."

    if expanded in FileTag._indexed_directories:
        _debug_log(f"folder_delete: cannot delete root – {expanded}", 2)
        status.fail_tool_call(tool_id, "Cannot delete root")
        return f"Error: Cannot delete indexed root folder: {expanded}"

    if not os.path.exists(expanded):
        _debug_log(f"folder_delete: not found – {expanded}", 2)
        status.fail_tool_call(tool_id, "Folder not found")
        return f"Error: Folder does not exist: {expanded}"

    if not os.path.isdir(expanded):
        _debug_log(f"folder_delete: not a folder – {expanded}", 2)
        status.fail_tool_call(tool_id, "Not a folder")
        return f"Error: Not a folder: {expanded}. Use note_delete to remove a note file."

    try:
        backup_path = backup_folder(expanded)
    except OSError as e:
        _debug_log(f"folder_delete: backup failed – {e}", 2)
        status.fail_tool_call(tool_id, "Backup failed")
        return f"Error: Could not create backup before deletion: {e}"

    try:
        prefix = expanded + os.sep
        FileTag._index = [
            (name, fp)
            for name, fp in FileTag._index
            if fp != expanded and not fp.startswith(prefix)
        ]
        FileTag._filepath_to_idx = {
            fp: idx for idx, (_, fp) in enumerate(FileTag._index)
        }

        shutil.rmtree(expanded)

        dir_name = Path(expanded).name
        status.complete_tool_call(tool_id, dir_name)
        return f"Successfully deleted folder: {expanded}\nBackup saved to: {backup_path}"
    except Exception as e:
        _debug_log(f"folder_delete: failed – {e}", 2)
        status.fail_tool_call(tool_id, str(e)[:30])
        return f"Error deleting folder: {e}"


# --- note browse tools ---


def _render_subtree(lines: list[str], current_dir: str, tree: dict[str, list[str]], indent: int):
    """Recursively render folders and notes as indented lines."""
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
def list_folder(path: str) -> str:
    """
    List all indexed notes in a specific folder (non-recursive).

    Args:
        path: The folder path to list (must be within an indexed folder).

    Returns:
        A list of note names in the folder, or an error description.
    """
    _tool_call_counter["list_folder"] += 1
    tool_id = f"list_folder_{_tool_call_counter['list_folder']}_{int(time.time() * 1000)}"
    status = _status_manager()

    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"list_folder: path not indexed – {path}", 2)
        status.fail_tool_call(tool_id, "Not in indexed folders")
        return f"Error: Path '{path}' is not within an indexed folder."

    if not os.path.isdir(expanded):
        _debug_log(f"list_folder: not a folder – {expanded}", 2)
        status.fail_tool_call(tool_id, "Not a folder")
        return f"Error: Not a folder: {expanded}"

    files = []
    for _basename, filepath in FileTag._index:
        if Path(filepath).parent == Path(expanded):
            files.append(Path(filepath).name)

    if not files:
        status.complete_tool_call(tool_id, "Empty")
        return f"No indexed notes in: {expanded}"

    files.sort()
    status.complete_tool_call(tool_id, f"{len(files)} notes")
    return f"Folder: {expanded}\n\n" + "\n".join(files)


@tool
def view_folder_structure() -> str:
    """
    Show the folder tree of all indexed folders and their notes.

    Returns:
        A tree-style listing of all indexed folders and notes.
    """
    _tool_call_counter["view_folder_structure"] += 1
    tool_id = f"view_folder_structure_{_tool_call_counter['view_folder_structure']}_{int(time.time() * 1000)}"
    status = _status_manager()

    if not FileTag._indexed_directories:
        status.complete_tool_call(tool_id, "No folders")
        return "No folders are currently indexed."

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

    status.complete_tool_call(tool_id, f"{len(FileTag._index)} notes")
    return "\n".join(lines)
