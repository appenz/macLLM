"""Shared helpers for file tools: path validation and backup."""

import os
import shutil
from datetime import datetime
from pathlib import Path

from macllm.tags.file_tag import FileTag

BACKUP_DIR = os.path.expanduser("~/.macllm-backup")


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
