"""General local file reads for user-referenced paths."""

from __future__ import annotations

import os
from pathlib import Path

from macllm.core.chat_history import add_source
from macllm.core.context import get_current_conversation
from macllm.tags.file_tag import FileTag
from macllm.tools._debug import macllm_tool, set_tool_message

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".tiff", ".bmp"}
DEFAULT_MAX_CHARS = 10_000
HARD_MAX_CHARS = 200 * 1024


def _resolve_readable_path(path: str) -> str | None:
    """Return an absolute path if it exists and is under an allowed root."""
    expanded = os.path.abspath(os.path.expanduser(path))
    if not os.path.exists(expanded):
        mount = FileTag.resolve_mount_path(path)
        if mount is None or not os.path.exists(mount):
            return None
        expanded = os.path.abspath(mount)

    allowed_roots: list[str] = []
    for indexed_dir in FileTag._indexed_directories:
        allowed_roots.append(os.path.abspath(indexed_dir))
    for name, mount_root in FileTag._mount_points.items():
        allowed_roots.append(os.path.abspath(mount_root))

    conv = get_current_conversation()
    if conv is not None:
        for granted in conv.get_granted_dirs():
            allowed_roots.append(os.path.abspath(granted))

    for root in allowed_roots:
        if expanded == root or expanded.startswith(root + os.sep):
            return expanded
    return None


@macllm_tool
def read_file(path: str, start: int = 0, max_chars: int = DEFAULT_MAX_CHARS) -> str:
    """
    Read a local file by path.

    Args:
        path: Absolute path, home-relative path, or mount-relative note path.
        start: Zero-based character offset for text files.
        max_chars: Maximum characters to return for text files (default 10000).

    Returns:
        Bounded text for text files, or an image observation for image files.
    """
    set_tool_message(f"Reading {path}")

    allowed = _resolve_readable_path(path)
    if allowed is None:
        return f"Error: Path '{path}' is not readable."

    if os.path.isdir(allowed):
        return f"Error: '{path}' is a directory. Use list_folder or grant access for shell tools."

    suffix = Path(allowed).suffix.lower()

    if suffix in IMAGE_EXTENSIONS:
        from PIL import Image
        try:
            img = Image.open(allowed)
            img.load()
        except Exception as exc:
            return f"Error reading image: {exc}"
        add_source("file", allowed)
        return img.copy()

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
        with open(allowed, "r", encoding="utf-8") as f:
            content = f.read(HARD_MAX_CHARS + 1)
            if "\0" in content:
                return "Error: File appears to be binary."
    except Exception as exc:
        return f"Error reading file: {exc}"

    total = len(content)
    if start >= total and total > 0:
        return f"Error: start {start} is beyond available content length {total}."

    end = min(start + max_chars, total)
    chunk = content[start:end]
    add_source("file", allowed)

    has_more = end < total or total > HARD_MAX_CHARS
    if has_more:
        shown_total = min(total, HARD_MAX_CHARS)
        return f"[file truncated, chars {start}-{end} of {shown_total}]\n\n{chunk}"
    return chunk
