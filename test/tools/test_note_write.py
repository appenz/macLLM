"""Tests for note_append, note_create, and note_modify (mount-path API)."""

import os
from pathlib import Path

from macllm.tools.note import note_append, note_create, note_modify, BACKUP_DIR
from macllm.tags.file_tag import FileTag

from .conftest import MOUNT_NAME


class TestNoteAppend:
    def test_append_to_existing_note(self, file_env):
        result = note_append(f"{MOUNT_NAME}/alpha.md", "New line")

        assert "Successfully appended" in result
        assert "New line" in open(str(file_env / "alpha.md")).read()

    def test_append_preserves_original_content(self, file_env):
        note_append(f"{MOUNT_NAME}/alpha.md", "Appended")

        content = open(str(file_env / "alpha.md")).read()
        assert content.startswith("Alpha content about travel")
        assert content.endswith("Appended")

    def test_append_adds_newline_separator(self, file_env):
        note_append(f"{MOUNT_NAME}/alpha.md", "First")
        note_append(f"{MOUNT_NAME}/alpha.md", "Second")

        content = open(str(file_env / "alpha.md")).read()
        assert "Alpha content about travel\nFirst\nSecond" in content

    def test_append_to_empty_note(self, file_env):
        empty = file_env / "empty.md"
        empty.write_text("")
        FileTag._index.append(("empty.md", str(empty)))

        result = note_append(f"{MOUNT_NAME}/empty.md", "Content")

        assert "Successfully appended" in result
        assert open(str(empty)).read() == "Content"

    def test_append_fails_nonexistent(self, file_env):
        result = note_append(f"{MOUNT_NAME}/missing.md", "text")
        assert "Error" in result
        assert "does not exist" in result

    def test_append_rejects_outside_indexed(self, file_env):
        result = note_append("/tmp/not-indexed/file.md", "text")
        assert "Error" in result
        assert "not within an indexed folder" in result


class TestNoteCreate:
    def test_create_new_note(self, file_env):
        result = note_create(f"{MOUNT_NAME}/new-note.md", "Brand new content")

        assert "Successfully created" in result
        assert os.path.exists(str(file_env / "new-note.md"))
        assert open(str(file_env / "new-note.md")).read() == "Brand new content"

    def test_create_adds_md_extension(self, file_env):
        result = note_create(f"{MOUNT_NAME}/auto-ext", "Content")

        assert "Successfully created" in result
        assert os.path.exists(str(file_env / "auto-ext.md"))

    def test_create_fails_if_exists(self, file_env):
        result = note_create(f"{MOUNT_NAME}/alpha.md", "Content")

        assert "Error" in result
        assert "already exists" in result

    def test_create_adds_to_index(self, file_env):
        note_create(f"{MOUNT_NAME}/indexed.md", "Content")
        assert any("indexed.md" in fp for _, fp in FileTag._index)

    def test_create_rejects_outside_indexed(self, file_env):
        result = note_create("/tmp/not-indexed/file.md", "Content")
        assert "Error" in result

    def test_create_fails_if_parent_folder_missing(self, file_env):
        result = note_create(f"{MOUNT_NAME}/no-such-dir/file.md", "Content")
        assert "Error" in result


class TestNoteModify:
    def test_modify_replaces_content(self, file_env):
        result = note_modify(f"{MOUNT_NAME}/alpha.md", "Completely new content")

        assert "Successfully modified" in result
        assert open(str(file_env / "alpha.md")).read() == "Completely new content"

    def test_modify_creates_backup(self, file_env):
        path = str(file_env / "alpha.md")
        original = open(path).read()
        result = note_modify(f"{MOUNT_NAME}/alpha.md", "Replaced")

        assert "Backup saved to:" in result
        backup_line = [l for l in result.split("\n") if "Backup" in l][0]
        backup_path = backup_line.split("Backup saved to: ")[1]
        assert os.path.exists(backup_path)
        assert open(backup_path).read() == original

    def test_modify_fails_nonexistent(self, file_env):
        result = note_modify(f"{MOUNT_NAME}/missing.md", "content")
        assert "Error" in result
        assert "does not exist" in result

    def test_modify_rejects_outside_indexed(self, file_env):
        result = note_modify("/tmp/not-indexed/file.md", "content")
        assert "Error" in result

    def test_modify_backup_collision_avoidance(self, file_env):
        note_modify(f"{MOUNT_NAME}/alpha.md", "Version 1")
        result2 = note_modify(f"{MOUNT_NAME}/alpha.md", "Version 2")

        assert "Backup saved to:" in result2
