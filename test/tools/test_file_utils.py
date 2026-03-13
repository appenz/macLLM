"""Tests for shared file utility helpers."""

import os
from pathlib import Path

import pytest

from macllm.tools.file import validate_indexed_path, backup_file, BACKUP_DIR
from macllm.tags.file_tag import FileTag


class TestValidateIndexedPath:
    def test_valid_path_in_indexed_dir(self, file_env):
        result = validate_indexed_path(str(file_env / "alpha.md"))
        assert result == str(file_env / "alpha.md")

    def test_valid_nested_path(self, file_env):
        result = validate_indexed_path(str(file_env / "subdir" / "gamma.md"))
        assert result is not None

    def test_rejects_outside_indexed(self, file_env):
        result = validate_indexed_path("/tmp/not-indexed/file.md")
        assert result is None

    def test_expands_tilde(self, file_env):
        home = os.path.expanduser("~")
        FileTag._indexed_directories = [home]
        result = validate_indexed_path("~/test-file.md")
        assert result == os.path.join(home, "test-file.md")
        FileTag._indexed_directories = [str(file_env)]

    def test_empty_indexed_dirs(self, file_env):
        FileTag._indexed_directories = []
        result = validate_indexed_path(str(file_env / "alpha.md"))
        assert result is None
        FileTag._indexed_directories = [str(file_env)]


class TestBackupFile:
    def test_creates_backup(self, file_env):
        path = str(file_env / "alpha.md")
        original = open(path).read()

        backup_path = backup_file(path)

        assert os.path.exists(backup_path)
        assert open(backup_path).read() == original

    def test_backup_in_correct_directory(self, file_env):
        path = str(file_env / "alpha.md")
        backup_path = backup_file(path)

        assert backup_path.startswith(BACKUP_DIR)

    def test_backup_name_format(self, file_env, monkeypatch):
        import macllm.tools.file as fu
        test_backup = str(file_env / "backups")
        monkeypatch.setattr(fu, "BACKUP_DIR", test_backup)

        path = str(file_env / "alpha.md")
        backup_path = backup_file(path)

        backup_name = Path(backup_path).name
        assert "alpha.md" in backup_name
        # Format: YYYY-MM-DD-HH:MM alpha.md (no collision suffix on first call)
        parts = backup_name.split(" ", 1)
        assert len(parts) == 2
        assert parts[1] == "alpha.md"

    def test_collision_avoidance(self, file_env):
        path = str(file_env / "alpha.md")

        b1 = backup_file(path)
        b2 = backup_file(path)

        assert b1 != b2
        assert os.path.exists(b1)
        assert os.path.exists(b2)

    def test_backup_nonexistent_raises(self, file_env):
        with pytest.raises(FileNotFoundError):
            backup_file(str(file_env / "nonexistent.md"))
