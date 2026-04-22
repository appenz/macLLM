"""Note tools: search, read, write, move, delete, browse, and manage folders for indexed notes."""

import os
import shutil
from datetime import datetime
from pathlib import Path

from macllm.tags.file_tag import FileTag
from macllm.tools._debug import macllm_tool

BACKUP_DIR = os.path.expanduser("~/.macllm-backup")


def validate_indexed_path(path: str) -> str | None:
    """Resolve *path* to an absolute path inside an indexed folder.

    Accepts mount-relative paths (``Notes/todo.md``) as well as absolute
    paths for backward compatibility.  Returns the absolute path string
    on success, ``None`` otherwise.
    """
    resolved = FileTag.resolve_mount_path(path)
    if resolved is not None:
        return resolved

    expanded = os.path.abspath(os.path.expanduser(path))
    for indexed_dir in FileTag._indexed_directories:
        if expanded.startswith(indexed_dir + os.sep) or expanded == indexed_dir:
            return expanded
    return None


def _display_path(abs_path: str) -> str:
    """Return the mount-relative form of *abs_path*, falling back to the raw path."""
    return FileTag.to_mount_path(abs_path) or abs_path


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


def _debug_log(message: str, level: int = 0) -> None:
    from macllm.macllm import MacLLM

    app = MacLLM._instance
    if app is not None:
        app.debug_log(message, level)


# --- note write tools ---


@macllm_tool
def note_append(path: str, text: str) -> str:
    """
    Append text to an existing note.

    Args:
        path: The note path, e.g. "Notes/todo.md" (mount-name/relative-path).
        text: The text content to append to the note.

    Returns:
        Success message with the note path, or an error description.
    """
    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"note_append: path not indexed – {path}", 2)
        return f"Error: Path '{path}' is not within an indexed folder."

    display = _display_path(expanded)

    if not os.path.exists(expanded):
        _debug_log(f"note_append: not found – {display}", 2)
        return f"Error: Note does not exist: {display}. Use note_create to create new notes."

    try:
        has_content = os.path.getsize(expanded) > 0
        with open(expanded, "a", encoding="utf-8") as f:
            if has_content:
                f.write("\n")
            f.write(text)
        return f"Successfully appended to: {display}"
    except Exception as e:
        _debug_log(f"note_append: write failed – {e}", 2)
        return f"Error writing to note: {e}"


@macllm_tool
def note_create(path: str, text: str) -> str:
    """
    Create a new note with the given content. Fails if the note already exists.

    Args:
        path: The note path, e.g. "Notes/todo.md" (mount-name/relative-path). Extension .md is added if missing.
        text: The text content to write to the new note.

    Returns:
        Success message with the note path, or an error description.
    """
    if not path.lower().endswith(FileTag.EXTENSIONS):
        path = path + ".md"

    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"note_create: path not indexed – {path}", 2)
        return f"Error: Path '{path}' is not within an indexed folder."

    display = _display_path(expanded)

    if os.path.exists(expanded):
        _debug_log(f"note_create: already exists – {display}", 2)
        return f"Error: Note already exists: {display}. Use note_append to add content."

    parent = Path(expanded).parent
    if not parent.exists():
        _debug_log(f"note_create: folder not found – {_display_path(str(parent))}", 2)
        return f"Error: Folder does not exist: {_display_path(str(parent))}"

    try:
        with open(expanded, "w", encoding="utf-8") as f:
            f.write(text)
        FileTag._index.append((Path(expanded).name.lower(), expanded))
        FileTag._index.sort(key=lambda t: t[0])
        return f"Successfully created: {display}"
    except Exception as e:
        _debug_log(f"note_create: failed – {e}", 2)
        return f"Error creating note: {e}"


@macllm_tool
def note_modify(path: str, new_content: str) -> str:
    """
    Replace the entire content of an existing note. A backup of the original is saved automatically.

    Args:
        path: The note path, e.g. "Notes/todo.md" (mount-name/relative-path).
        new_content: The new content that will replace the note's current content.

    Returns:
        Success message with the note path and backup location, or an error description.
    """
    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"note_modify: path not indexed – {path}", 2)
        return f"Error: Path '{path}' is not within an indexed folder."

    display = _display_path(expanded)

    if not os.path.exists(expanded):
        _debug_log(f"note_modify: not found – {display}", 2)
        return f"Error: Note does not exist: {display}."

    try:
        backup_path = backup_file(expanded)
    except OSError as e:
        _debug_log(f"note_modify: backup failed – {e}", 2)
        return f"Error: Could not create backup: {e}"

    try:
        with open(expanded, "w", encoding="utf-8") as f:
            f.write(new_content)
        return f"Successfully modified: {display}\nBackup saved to: {backup_path}"
    except Exception as e:
        _debug_log(f"note_modify: write failed – {e}", 2)
        return f"Error modifying note: {e}"


# --- note search tools ---


@macllm_tool
def search_notes(query: str) -> str:
    """
    Search indexed notes using semantic similarity.

    Args:
        query: The search query to find relevant notes.

    Returns:
        Top 5 matching notes with path, filename, relevance score, and first 1000 characters of content.
    """
    try:
        results = FileTag.search(query)
        if not results:
            return "No matching notes found"

        output_parts = []
        for _file_id, score, filepath, preview, truncated in results:
            display = _display_path(filepath)
            filename = Path(filepath).name
            note_status = "(truncated)" if truncated else "(complete)"
            output_parts.append(
                f"[{display}] {filename} {note_status}\n"
                f"Score: {score:.3f}\n{preview}\n"
            )

        return "\n---\n".join(output_parts)

    except Exception as e:
        _debug_log(f"search_notes: failed – {e}", 2)
        raise


@macllm_tool
def read_note(path: str) -> str:
    """
    Read the full content of a note by its path.

    Args:
        path: The note path, e.g. "Notes/todo.md" (mount-name/relative-path).

    Returns:
        The full content of the note (up to 10,000 characters).
    """
    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"read_note: path not indexed – {path}", 2)
        return f"Error: Path '{path}' is not within an indexed folder."

    display = _display_path(expanded)

    if not Path(expanded).is_file():
        _debug_log(f"read_note: not found – {display}", 2)
        return f"Error: Note not found: {display}"

    try:
        with open(expanded, "r", encoding="utf-8") as f:
            content = f.read(FileTag.MAX_FULL_FILE_LEN)
        filename = Path(expanded).name
        return f"Note: {filename}\n\n{content}"
    except Exception as e:
        _debug_log(f"read_note: failed – {e}", 2)
        return f"Error reading note: {e}"


@macllm_tool
def note_resolve_path(path: str) -> str:
    """
    Resolve a note path to its absolute filesystem path.

    Args:
        path: The note path, e.g. "Notes/todo.md" (mount-name/relative-path).

    Returns:
        The absolute filesystem path, or an error if the path is not in an indexed folder.
    """
    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"note_resolve_path: path not indexed – {path}", 2)
        return f"Error: Path '{path}' is not within an indexed folder."

    return expanded


# --- note ops tools ---


@macllm_tool
def note_move(source_path: str, dest_path: str) -> str:
    """
    Move or rename a note within indexed folders. Fails if the destination already exists.

    Args:
        source_path: The current note path, e.g. "Notes/old.md" (mount-name/relative-path).
        dest_path: The new note path, e.g. "Notes/new.md" (mount-name/relative-path).

    Returns:
        Success message, or an error description.
    """
    src = validate_indexed_path(source_path)
    if src is None:
        _debug_log(f"note_move: source not indexed – {source_path}", 2)
        return f"Error: Source path '{source_path}' is not within an indexed folder."

    src_display = _display_path(src)

    if not os.path.exists(src):
        _debug_log(f"note_move: source not found – {src_display}", 2)
        return f"Error: Source note does not exist: {src_display}"

    dst = validate_indexed_path(dest_path)
    if dst is None:
        _debug_log(f"note_move: dest not indexed – {dest_path}", 2)
        return f"Error: Destination path '{dest_path}' is not within an indexed folder."

    dst_display = _display_path(dst)

    if os.path.exists(dst):
        _debug_log(f"note_move: dest exists – {dst_display}", 2)
        return f"Error: Destination already exists: {dst_display}. Will not overwrite."

    dst_parent = Path(dst).parent
    if not dst_parent.exists():
        _debug_log(f"note_move: dest folder not found – {_display_path(str(dst_parent))}", 2)
        return f"Error: Destination folder does not exist: {_display_path(str(dst_parent))}"

    try:
        shutil.move(src, dst)

        FileTag._index = [
            (name, fp) for name, fp in FileTag._index if fp != src
        ]
        FileTag._index.append((Path(dst).name.lower(), dst))
        FileTag._index.sort(key=lambda t: t[0])

        return f"Successfully moved: {src_display} -> {dst_display}"
    except Exception as e:
        _debug_log(f"note_move: failed – {e}", 2)
        return f"Error moving note: {e}"


@macllm_tool
def note_delete(path: str) -> str:
    """
    Delete a note. A backup is saved automatically before deletion.

    Args:
        path: The note path to delete, e.g. "Notes/todo.md" (mount-name/relative-path).

    Returns:
        Success message with the backup location, or an error description.
    """
    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"note_delete: path not indexed – {path}", 2)
        return f"Error: Path '{path}' is not within an indexed folder."

    display = _display_path(expanded)

    if not os.path.exists(expanded):
        _debug_log(f"note_delete: not found – {display}", 2)
        return f"Error: Note does not exist: {display}"

    try:
        backup_path = backup_file(expanded)
    except OSError as e:
        _debug_log(f"note_delete: backup failed – {e}", 2)
        return f"Error: Could not create backup before deletion: {e}"

    try:
        os.remove(expanded)

        FileTag._index = [
            (name, fp) for name, fp in FileTag._index if fp != expanded
        ]

        return f"Successfully deleted: {display}\nBackup saved to: {backup_path}"
    except Exception as e:
        _debug_log(f"note_delete: failed – {e}", 2)
        return f"Error deleting note: {e}"


# --- folder tools ---


@macllm_tool
def folder_create(path: str) -> str:
    """
    Create a new empty folder inside an indexed directory. The parent folder must already exist.

    Args:
        path: The folder path, e.g. "Notes/projects" (mount-name/relative-path).

    Returns:
        Success message with the folder path, or an error description.
    """
    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"folder_create: path not indexed – {path}", 2)
        return f"Error: Path '{path}' is not within an indexed folder."

    display = _display_path(expanded)

    if os.path.exists(expanded):
        if os.path.isdir(expanded):
            _debug_log(f"folder_create: already exists – {display}", 2)
            return f"Error: Folder already exists: {display}"
        _debug_log(f"folder_create: path is a file – {display}", 2)
        return f"Error: Path exists but is not a folder: {display}"

    parent = Path(expanded).parent
    if not parent.exists():
        _debug_log(f"folder_create: parent not found – {_display_path(str(parent))}", 2)
        return f"Error: Parent folder does not exist: {_display_path(str(parent))}"

    try:
        os.mkdir(expanded)
        return f"Successfully created folder: {display}"
    except Exception as e:
        _debug_log(f"folder_create: failed – {e}", 2)
        return f"Error creating folder: {e}"


@macllm_tool
def folder_delete(path: str) -> str:
    """
    Delete a folder and all of its contents. A backup of the entire folder tree is saved first.

    Cannot delete a mount-point root (only subfolders within it).

    Args:
        path: The folder path to delete, e.g. "Notes/old-project" (mount-name/relative-path).

    Returns:
        Success message with the backup location, or an error description.
    """
    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"folder_delete: path not indexed – {path}", 2)
        return f"Error: Path '{path}' is not within an indexed folder."

    display = _display_path(expanded)

    if expanded in FileTag._indexed_directories:
        _debug_log(f"folder_delete: cannot delete root – {display}", 2)
        return f"Error: Cannot delete indexed root folder: {display}"

    if not os.path.exists(expanded):
        _debug_log(f"folder_delete: not found – {display}", 2)
        return f"Error: Folder does not exist: {display}"

    if not os.path.isdir(expanded):
        _debug_log(f"folder_delete: not a folder – {display}", 2)
        return f"Error: Not a folder: {display}. Use note_delete to remove a note file."

    try:
        backup_path = backup_folder(expanded)
    except OSError as e:
        _debug_log(f"folder_delete: backup failed – {e}", 2)
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

        return f"Successfully deleted folder: {display}\nBackup saved to: {backup_path}"
    except Exception as e:
        _debug_log(f"folder_delete: failed – {e}", 2)
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


@macllm_tool
def list_folder(path: str) -> str:
    """
    List all indexed notes in a specific folder (non-recursive).

    Args:
        path: The folder path to list, e.g. "Notes" or "Notes/projects" (mount-name/relative-path).

    Returns:
        A list of note names in the folder, or an error description.
    """
    expanded = validate_indexed_path(path)
    if expanded is None:
        _debug_log(f"list_folder: path not indexed – {path}", 2)
        return f"Error: Path '{path}' is not within an indexed folder."

    display = _display_path(expanded)

    if not os.path.isdir(expanded):
        _debug_log(f"list_folder: not a folder – {display}", 2)
        return f"Error: Not a folder: {display}"

    subdirs = []
    try:
        for entry in os.scandir(expanded):
            if entry.is_dir() and not entry.name.startswith("."):
                subdirs.append(entry.name)
    except OSError:
        pass

    files = []
    expanded_path = Path(expanded)
    for _basename, filepath in FileTag._index:
        if Path(filepath).parent == expanded_path:
            files.append(Path(filepath).name)

    if not subdirs and not files:
        return f"No indexed notes or subfolders in: {display}"

    lines = []
    for d in sorted(subdirs):
        lines.append(f"{d}/")
    for f in sorted(files):
        lines.append(f)

    return f"Folder: {display}\n\n" + "\n".join(lines)


@macllm_tool
def find_folder(query: str) -> str:
    """
    Search for folders by name across all indexed mounts. Case-insensitive substring match.

    Args:
        query: The folder name to search for, e.g. "pitches" matches "Pitches", "Active Pitch Docs", etc.

    Returns:
        A list of matching folder paths (mount-relative), or a message if none found.
    """
    query_lower = query.lower()
    matches = []

    for mount_name, root_dir in FileTag._mount_points.items():
        if query_lower in mount_name.lower():
            matches.append(mount_name)

        for dirpath, dirnames, _ in os.walk(root_dir):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for d in dirnames:
                if query_lower in d.lower():
                    abs_path = os.path.join(dirpath, d)
                    mount_path = FileTag.to_mount_path(abs_path)
                    if mount_path:
                        matches.append(mount_path)

    if not matches:
        return "No matching folders found"

    matches.sort()
    return "\n".join(matches)


@macllm_tool
def view_folder_structure() -> str:
    """
    Show the folder tree of all indexed folders and their notes.

    Returns:
        A tree-style listing of all indexed folders and notes.
    """
    if not FileTag._mount_points:
        return "No folders are currently indexed."

    tree: dict[str, list[str]] = {}

    for _basename, filepath in FileTag._index:
        parent = str(Path(filepath).parent)
        if parent not in tree:
            tree[parent] = []
        tree[parent].append(Path(filepath).name)

    lines = []
    for mount_name, root_dir in FileTag._mount_points.items():
        lines.append(f"{mount_name}/")
        _render_subtree(lines, root_dir, tree, indent=1)

    return "\n".join(lines)
