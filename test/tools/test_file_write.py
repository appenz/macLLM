"""Tests for file_append, file_create, and file_modify (path-based API)."""

import os
from pathlib import Path

from macllm.tools.file import file_append, file_create, file_modify, BACKUP_DIR
from macllm.tags.file_tag import FileTag


class TestFileAppend:
    def test_append_to_existing_file(self, file_env):
        path = str(file_env / "alpha.md")
        result = file_append(path, "New line")

        assert "Successfully appended" in result
        assert "New line" in open(path).read()

    def test_append_preserves_original_content(self, file_env):
        path = str(file_env / "alpha.md")
        file_append(path, "Appended")

        content = open(path).read()
        assert content.startswith("Alpha content about travel")
        assert content.endswith("Appended")

    def test_append_adds_newline_separator(self, file_env):
        path = str(file_env / "alpha.md")
        file_append(path, "First")
        file_append(path, "Second")

        content = open(path).read()
        assert "Alpha content about travel\nFirst\nSecond" in content

    def test_append_to_empty_file(self, file_env):
        empty = file_env / "empty.md"
        empty.write_text("")
        FileTag._index.append(("empty.md", str(empty)))

        result = file_append(str(empty), "Content")

        assert "Successfully appended" in result
        assert open(str(empty)).read() == "Content"

    def test_append_fails_nonexistent(self, file_env):
        result = file_append(str(file_env / "missing.md"), "text")
        assert "Error" in result
        assert "does not exist" in result

    def test_append_rejects_outside_indexed(self, file_env):
        result = file_append("/tmp/not-indexed/file.md", "text")
        assert "Error" in result
        assert "not within an indexed directory" in result


class TestFileCreate:
    def test_create_new_file(self, file_env):
        path = str(file_env / "new-note.md")
        result = file_create(path, "Brand new content")

        assert "Successfully created" in result
        assert os.path.exists(path)
        assert open(path).read() == "Brand new content"

    def test_create_adds_md_extension(self, file_env):
        result = file_create(str(file_env / "auto-ext"), "Content")

        assert "Successfully created" in result
        assert os.path.exists(str(file_env / "auto-ext.md"))

    def test_create_fails_if_exists(self, file_env):
        result = file_create(str(file_env / "alpha.md"), "Content")

        assert "Error" in result
        assert "already exists" in result

    def test_create_adds_to_index(self, file_env):
        file_create(str(file_env / "indexed.md"), "Content")
        assert any("indexed.md" in fp for _, fp in FileTag._index)

    def test_create_rejects_outside_indexed(self, file_env):
        result = file_create("/tmp/not-indexed/file.md", "Content")
        assert "Error" in result

    def test_create_fails_if_parent_dir_missing(self, file_env):
        result = file_create(str(file_env / "no-such-dir" / "file.md"), "Content")
        assert "Error" in result


class TestFileModify:
    def test_modify_replaces_content(self, file_env):
        path = str(file_env / "alpha.md")
        result = file_modify(path, "Completely new content")

        assert "Successfully modified" in result
        assert open(path).read() == "Completely new content"

    def test_modify_creates_backup(self, file_env):
        path = str(file_env / "alpha.md")
        original = open(path).read()
        result = file_modify(path, "Replaced")

        assert "Backup saved to:" in result
        backup_line = [l for l in result.split("\n") if "Backup" in l][0]
        backup_path = backup_line.split("Backup saved to: ")[1]
        assert os.path.exists(backup_path)
        assert open(backup_path).read() == original

    def test_modify_fails_nonexistent(self, file_env):
        result = file_modify(str(file_env / "missing.md"), "content")
        assert "Error" in result
        assert "does not exist" in result

    def test_modify_rejects_outside_indexed(self, file_env):
        result = file_modify("/tmp/not-indexed/file.md", "content")
        assert "Error" in result

    def test_modify_backup_collision_avoidance(self, file_env):
        path = str(file_env / "alpha.md")

        file_modify(path, "Version 1")
        result2 = file_modify(path, "Version 2")

        assert "Backup saved to:" in result2
