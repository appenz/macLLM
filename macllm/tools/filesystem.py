"""Agent-callable virtual filesystem operations."""

from __future__ import annotations

import os
import shutil

from PIL import Image

from macllm.core.chat_history import add_source
from macllm.core.virtual_filesystem import (
    FilesystemError,
    list_virtual_directory,
    resolve_path,
)
from macllm.tags.file_tag import FileTag
from macllm.tools._debug import macllm_tool, set_tool_message

FILESYSTEM_TOOLS = [
    "read_file",
    "write_file",
    "append_file",
    "list_directory",
    "copy_file",
    "delete_file",
    "create_directory",
]

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".tiff", ".bmp"}
DEFAULT_MAX_CHARS = 10_000
HARD_MAX_CHARS = 200 * 1024


def _error(exc: Exception) -> str:
    return f"Error: {exc}"


def _refresh_index(mount) -> None:
    if mount.index:
        FileTag._reindex_event.set()


@macllm_tool
def read_file(path: str, start: int = 0, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """Read a text or image file.

    Args:
        path: Absolute virtual path to read.
        start: Zero-based character offset for text files.
        max_chars: Maximum characters to return for text files.
    """
    set_tool_message(f"Reading {path}")
    try:
        target = resolve_path(path)
    except FilesystemError as exc:
        return _error(exc)

    if target.canonical.is_dir():
        return _error(
            FilesystemError(f"'{target.virtual}' is a directory. Use list_directory.")
        )

    if target.canonical.suffix.lower() in IMAGE_EXTENSIONS:
        try:
            with Image.open(target.canonical) as image:
                image.load()
                result = image.copy()
        except Exception as exc:
            return f"Error reading image: {exc}"
        add_source("file", str(target.canonical))
        return result

    try:
        start = int(start)
        max_chars = int(max_chars)
    except (TypeError, ValueError):
        return "Error: start and max_chars must be integers."
    if start < 0:
        return "Error: start must be >= 0."
    if max_chars <= 0:
        return "Error: max_chars must be > 0."
    max_chars = min(max_chars, HARD_MAX_CHARS)

    try:
        with target.canonical.open("r", encoding="utf-8") as handle:
            content = handle.read(HARD_MAX_CHARS + 1)
    except Exception as exc:
        return f"Error reading file: {exc}"
    if "\0" in content:
        return "Error: File appears to be binary."

    total = len(content)
    if start >= total and total > 0:
        return f"Error: start {start} is beyond available content length {total}."

    end = min(start + max_chars, total)
    chunk = content[start:end]
    add_source("file", str(target.canonical))
    if end < total:
        shown_total = min(total, HARD_MAX_CHARS)
        return f"[file truncated, chars {start}-{end} of {shown_total}]\n\n{chunk}"
    return chunk


@macllm_tool
def write_file(path: str, content: str) -> str:
    """Create or replace a text file.

    Args:
        path: Absolute virtual path to write.
        content: Complete text content.
    """
    set_tool_message(f"Writing {path}")
    try:
        target = resolve_path(path, write=True)
        if not target.path.parent.is_dir():
            return _error(FilesystemError("Parent directory does not exist."))
        flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(target.path, flags, 0o644), "w", encoding="utf-8") as handle:
            handle.write(content)
        _refresh_index(target.mount)
        return f"Wrote {target.virtual}"
    except Exception as exc:
        return _error(exc)


@macllm_tool
def append_file(path: str, content: str) -> str:
    """Append text to a file, creating it if necessary.

    Args:
        path: Absolute virtual path to append to.
        content: Text to append.
    """
    set_tool_message(f"Appending to {path}")
    try:
        target = resolve_path(path, write=True)
        if not target.path.parent.is_dir():
            return _error(FilesystemError("Parent directory does not exist."))
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND | getattr(os, "O_NOFOLLOW", 0)
        with os.fdopen(os.open(target.path, flags, 0o644), "a", encoding="utf-8") as handle:
            handle.write(content)
        _refresh_index(target.mount)
        return f"Appended to {target.virtual}"
    except Exception as exc:
        return _error(exc)


@macllm_tool
def list_directory(path: str) -> str:
    """List the immediate contents of a directory.

    Args:
        path: Absolute virtual directory path.
    """
    set_tool_message(f"Listing {path}")
    try:
        virtual = list_virtual_directory(path)
        virtual_entries = set(virtual or [])
        try:
            target = resolve_path(path)
        except FilesystemError:
            if virtual is not None:
                return "\n".join(sorted(virtual_entries)) or "(empty)"
            raise
        if not target.canonical.is_dir():
            return _error(FilesystemError(f"'{target.virtual}' is not a directory."))
        entries = virtual_entries | {
            (f"{entry.name}/" if entry.is_dir(follow_symlinks=False) else entry.name)
            for entry in os.scandir(target.canonical)
        }
        return "\n".join(sorted(entries)) or "(empty)"
    except Exception as exc:
        return _error(exc)


@macllm_tool
def copy_file(source: str, destination: str) -> str:
    """Copy a file or directory without overwriting the destination.

    Args:
        source: Absolute virtual source path.
        destination: Absolute virtual destination path.
    """
    set_tool_message(f"Copying {source} to {destination}")
    try:
        src = resolve_path(source)
        dst = resolve_path(destination, write=True)
        if not src.canonical.exists():
            return _error(FilesystemError(f"Source '{src.virtual}' does not exist."))
        if dst.path.exists() or dst.path.is_symlink():
            return _error(FilesystemError(f"Destination '{dst.virtual}' already exists."))
        if not dst.path.parent.is_dir():
            return _error(FilesystemError("Destination parent directory does not exist."))
        if src.canonical.is_dir():
            if any(item.is_symlink() for item in src.canonical.rglob("*")):
                return _error(FilesystemError("Directories containing symlinks cannot be copied."))
            shutil.copytree(src.canonical, dst.path)
        else:
            shutil.copy2(src.canonical, dst.path)
        _refresh_index(dst.mount)
        return f"Copied {src.virtual} to {dst.virtual}"
    except Exception as exc:
        return _error(exc)


@macllm_tool
def delete_file(path: str, recursive: bool = False) -> str:
    """Delete a file, symlink, or an explicitly recursive directory.

    Args:
        path: Absolute virtual path to delete.
        recursive: Allow deletion of a directory and its contents.
    """
    set_tool_message(f"Deleting {path}")
    try:
        target = resolve_path(path, write=True, deleting=True)
        if target.virtual == target.mount.virtual:
            return _error(FilesystemError("Filesystem mount roots cannot be deleted."))
        if target.path.is_symlink() or target.path.is_file():
            target.path.unlink()
        elif target.path.is_dir():
            if not recursive:
                return _error(FilesystemError("Directory deletion requires recursive=True."))
            shutil.rmtree(target.path)
        else:
            return _error(FilesystemError(f"Path '{target.virtual}' does not exist."))
        _refresh_index(target.mount)
        return f"Deleted {target.virtual}"
    except Exception as exc:
        return _error(exc)


@macllm_tool
def create_directory(path: str) -> str:
    """Create one directory whose parent already exists.

    Args:
        path: Absolute virtual path for the new directory.
    """
    set_tool_message(f"Creating directory {path}")
    try:
        target = resolve_path(path, write=True)
        if not target.path.parent.is_dir():
            return _error(FilesystemError("Parent directory does not exist."))
        target.path.mkdir()
        _refresh_index(target.mount)
        return f"Created {target.virtual}"
    except Exception as exc:
        return _error(exc)
