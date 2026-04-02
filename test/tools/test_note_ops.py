"""Tests for note_move and note_delete."""

import os
from pathlib import Path

from macllm.tools.note import note_move, note_delete, folder_create, folder_delete
from macllm.tags.file_tag import FileTag


class TestNoteMove:
    def test_move_renames_note(self, file_env):
        src = str(file_env / "alpha.md")
        dst = str(file_env / "renamed.md")
        result = note_move(src, dst)

        assert "Successfully moved" in result
        assert not os.path.exists(src)
        assert os.path.exists(dst)
        assert open(dst).read() == "Alpha content about travel"

    def test_move_updates_index(self, file_env):
        src = str(file_env / "alpha.md")
        dst = str(file_env / "renamed.md")
        note_move(src, dst)

        paths = [fp for _, fp in FileTag._index]
        assert src not in paths
        assert dst in paths

    def test_move_refuses_overwrite(self, file_env):
        src = str(file_env / "alpha.md")
        dst = str(file_env / "beta.txt")
        result = note_move(src, dst)

        assert "Error" in result
        assert "already exists" in result
        assert os.path.exists(src)

    def test_move_fails_source_missing(self, file_env):
        result = note_move(str(file_env / "missing.md"), str(file_env / "dst.md"))
        assert "Error" in result
        assert "does not exist" in result

    def test_move_rejects_source_outside_indexed(self, file_env):
        result = note_move("/tmp/outside.md", str(file_env / "dst.md"))
        assert "Error" in result
        assert "not within an indexed folder" in result

    def test_move_rejects_dest_outside_indexed(self, file_env):
        result = note_move(str(file_env / "alpha.md"), "/tmp/outside.md")
        assert "Error" in result
        assert "not within an indexed folder" in result

    def test_move_into_subfolder(self, file_env):
        src = str(file_env / "alpha.md")
        dst = str(file_env / "subdir" / "moved.md")
        result = note_move(src, dst)

        assert "Successfully moved" in result
        assert os.path.exists(dst)

    def test_move_fails_dest_folder_missing(self, file_env):
        src = str(file_env / "alpha.md")
        dst = str(file_env / "nodir" / "file.md")
        result = note_move(src, dst)

        assert "Error" in result
        assert "does not exist" in result


class TestNoteDelete:
    def test_delete_removes_note(self, file_env):
        path = str(file_env / "alpha.md")
        result = note_delete(path)

        assert "Successfully deleted" in result
        assert not os.path.exists(path)

    def test_delete_creates_backup(self, file_env):
        path = str(file_env / "alpha.md")
        original = open(path).read()
        result = note_delete(path)

        assert "Backup saved to:" in result
        backup_line = [l for l in result.split("\n") if "Backup" in l][0]
        backup_path = backup_line.split("Backup saved to: ")[1]
        assert os.path.exists(backup_path)
        assert open(backup_path).read() == original

    def test_delete_removes_from_index(self, file_env):
        path = str(file_env / "alpha.md")
        note_delete(path)

        paths = [fp for _, fp in FileTag._index]
        assert path not in paths

    def test_delete_fails_nonexistent(self, file_env):
        result = note_delete(str(file_env / "missing.md"))
        assert "Error" in result
        assert "does not exist" in result

    def test_delete_rejects_outside_indexed(self, file_env):
        result = note_delete("/tmp/not-indexed/file.md")
        assert "Error" in result
        assert "not within an indexed folder" in result


class TestFolderCreate:
    def test_creates_folder(self, file_env):
        new_dir = file_env / "new_folder"
        result = folder_create(str(new_dir))

        assert "Successfully created folder" in result
        assert new_dir.is_dir()

    def test_fails_if_exists(self, file_env):
        result = folder_create(str(file_env / "subdir"))
        assert "Error" in result
        assert "already exists" in result

    def test_fails_parent_missing(self, file_env):
        result = folder_create(str(file_env / "missing_parent" / "nested"))
        assert "Error" in result
        assert "does not exist" in result

    def test_rejects_outside_indexed(self, file_env):
        result = folder_create("/tmp/not-indexed/folder")
        assert "Error" in result
        assert "not within an indexed folder" in result


class TestFolderDelete:
    def test_deletes_folder_and_contents(self, file_env):
        subdir = file_env / "subdir"
        result = folder_delete(str(subdir))

        assert "Successfully deleted folder" in result
        assert not subdir.exists()

    def test_creates_backup(self, file_env):
        subdir = file_env / "subdir"
        result = folder_delete(str(subdir))

        assert "Backup saved to:" in result
        backup_line = [l for l in result.split("\n") if "Backup" in l][0]
        backup_path = backup_line.split("Backup saved to: ")[1]
        assert os.path.isdir(backup_path)
        assert os.path.exists(os.path.join(backup_path, "gamma.md"))

    def test_removes_indexed_notes_under_folder(self, file_env):
        gamma = str(file_env / "subdir" / "gamma.md")
        folder_delete(str(file_env / "subdir"))

        paths = [fp for _, fp in FileTag._index]
        assert gamma not in paths

    def test_rebuilds_filepath_to_idx(self, file_env):
        folder_delete(str(file_env / "subdir"))
        for idx, (_, fp) in enumerate(FileTag._index):
            assert FileTag._filepath_to_idx[fp] == idx

    def test_fails_nonexistent(self, file_env):
        result = folder_delete(str(file_env / "missing_dir"))
        assert "Error" in result
        assert "does not exist" in result

    def test_rejects_root_indexed_folder(self, file_env):
        result = folder_delete(str(file_env))
        assert "Error" in result
        assert "root" in result.lower() or "indexed root" in result.lower()

    def test_rejects_note_file(self, file_env):
        result = folder_delete(str(file_env / "alpha.md"))
        assert "Error" in result
        assert "not a folder" in result.lower()

    def test_rejects_outside_indexed(self, file_env):
        result = folder_delete("/tmp/not-indexed/folder")
        assert "Error" in result
        assert "not within an indexed folder" in result
