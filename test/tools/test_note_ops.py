"""Tests for note_move and note_delete (mount-path API)."""

import os
from pathlib import Path

from macllm.tools.note import note_move, note_delete, folder_create, folder_delete
from macllm.tags.file_tag import FileTag

from .conftest import MOUNT_NAME


class TestNoteMove:
    def test_move_renames_note(self, file_env):
        result = note_move(f"{MOUNT_NAME}/alpha.md", f"{MOUNT_NAME}/renamed.md")

        assert "Successfully moved" in result
        assert not os.path.exists(str(file_env / "alpha.md"))
        assert os.path.exists(str(file_env / "renamed.md"))
        assert open(str(file_env / "renamed.md")).read() == "Alpha content about travel"

    def test_move_updates_index(self, file_env):
        src_abs = str(file_env / "alpha.md")
        dst_abs = str(file_env / "renamed.md")
        note_move(f"{MOUNT_NAME}/alpha.md", f"{MOUNT_NAME}/renamed.md")

        paths = [fp for _, fp in FileTag._index]
        assert src_abs not in paths
        assert dst_abs in paths

    def test_move_refuses_overwrite(self, file_env):
        result = note_move(f"{MOUNT_NAME}/alpha.md", f"{MOUNT_NAME}/beta.txt")

        assert "Error" in result
        assert "already exists" in result
        assert os.path.exists(str(file_env / "alpha.md"))

    def test_move_fails_source_missing(self, file_env):
        result = note_move(f"{MOUNT_NAME}/missing.md", f"{MOUNT_NAME}/dst.md")
        assert "Error" in result
        assert "does not exist" in result

    def test_move_rejects_source_outside_indexed(self, file_env):
        result = note_move("/tmp/outside.md", f"{MOUNT_NAME}/dst.md")
        assert "Error" in result
        assert "not within an indexed folder" in result

    def test_move_rejects_dest_outside_indexed(self, file_env):
        result = note_move(f"{MOUNT_NAME}/alpha.md", "/tmp/outside.md")
        assert "Error" in result
        assert "not within an indexed folder" in result

    def test_move_into_subfolder(self, file_env):
        result = note_move(f"{MOUNT_NAME}/alpha.md", f"{MOUNT_NAME}/subdir/moved.md")

        assert "Successfully moved" in result
        assert os.path.exists(str(file_env / "subdir" / "moved.md"))

    def test_move_fails_dest_folder_missing(self, file_env):
        result = note_move(f"{MOUNT_NAME}/alpha.md", f"{MOUNT_NAME}/nodir/file.md")

        assert "Error" in result
        assert "does not exist" in result

    def test_move_output_uses_mount_paths(self, file_env):
        result = note_move(f"{MOUNT_NAME}/alpha.md", f"{MOUNT_NAME}/renamed.md")
        assert f"{MOUNT_NAME}/alpha.md" in result
        assert f"{MOUNT_NAME}/renamed.md" in result


class TestNoteDelete:
    def test_delete_removes_note(self, file_env):
        result = note_delete(f"{MOUNT_NAME}/alpha.md")

        assert "Successfully deleted" in result
        assert not os.path.exists(str(file_env / "alpha.md"))

    def test_delete_creates_backup(self, file_env):
        path = str(file_env / "alpha.md")
        original = open(path).read()
        result = note_delete(f"{MOUNT_NAME}/alpha.md")

        assert "Backup saved to:" in result
        backup_line = [l for l in result.split("\n") if "Backup" in l][0]
        backup_path = backup_line.split("Backup saved to: ")[1]
        assert os.path.exists(backup_path)
        assert open(backup_path).read() == original

    def test_delete_removes_from_index(self, file_env):
        abs_path = str(file_env / "alpha.md")
        note_delete(f"{MOUNT_NAME}/alpha.md")

        paths = [fp for _, fp in FileTag._index]
        assert abs_path not in paths

    def test_delete_fails_nonexistent(self, file_env):
        result = note_delete(f"{MOUNT_NAME}/missing.md")
        assert "Error" in result
        assert "does not exist" in result

    def test_delete_rejects_outside_indexed(self, file_env):
        result = note_delete("/tmp/not-indexed/file.md")
        assert "Error" in result
        assert "not within an indexed folder" in result

    def test_delete_output_uses_mount_path(self, file_env):
        result = note_delete(f"{MOUNT_NAME}/alpha.md")
        assert f"{MOUNT_NAME}/alpha.md" in result


class TestFolderCreate:
    def test_creates_folder(self, file_env):
        result = folder_create(f"{MOUNT_NAME}/new_folder")

        assert "Successfully created folder" in result
        assert (file_env / "new_folder").is_dir()

    def test_fails_if_exists(self, file_env):
        result = folder_create(f"{MOUNT_NAME}/subdir")
        assert "Error" in result
        assert "already exists" in result

    def test_fails_parent_missing(self, file_env):
        result = folder_create(f"{MOUNT_NAME}/missing_parent/nested")
        assert "Error" in result
        assert "does not exist" in result

    def test_rejects_outside_indexed(self, file_env):
        result = folder_create("/tmp/not-indexed/folder")
        assert "Error" in result
        assert "not within an indexed folder" in result


class TestFolderDelete:
    def test_deletes_folder_and_contents(self, file_env):
        result = folder_delete(f"{MOUNT_NAME}/subdir")

        assert "Successfully deleted folder" in result
        assert not (file_env / "subdir").exists()

    def test_creates_backup(self, file_env):
        result = folder_delete(f"{MOUNT_NAME}/subdir")

        assert "Backup saved to:" in result
        backup_line = [l for l in result.split("\n") if "Backup" in l][0]
        backup_path = backup_line.split("Backup saved to: ")[1]
        assert os.path.isdir(backup_path)
        assert os.path.exists(os.path.join(backup_path, "gamma.md"))

    def test_removes_indexed_notes_under_folder(self, file_env):
        gamma = str(file_env / "subdir" / "gamma.md")
        folder_delete(f"{MOUNT_NAME}/subdir")

        paths = [fp for _, fp in FileTag._index]
        assert gamma not in paths

    def test_rebuilds_filepath_to_idx(self, file_env):
        folder_delete(f"{MOUNT_NAME}/subdir")
        for idx, (_, fp) in enumerate(FileTag._index):
            assert FileTag._filepath_to_idx[fp] == idx

    def test_fails_nonexistent(self, file_env):
        result = folder_delete(f"{MOUNT_NAME}/missing_dir")
        assert "Error" in result
        assert "does not exist" in result

    def test_rejects_root_indexed_folder(self, file_env):
        result = folder_delete(MOUNT_NAME)
        assert "Error" in result
        assert "root" in result.lower() or "indexed root" in result.lower()

    def test_rejects_note_file(self, file_env):
        result = folder_delete(f"{MOUNT_NAME}/alpha.md")
        assert "Error" in result
        assert "not a folder" in result.lower()

    def test_rejects_outside_indexed(self, file_env):
        result = folder_delete("/tmp/not-indexed/folder")
        assert "Error" in result
        assert "not within an indexed folder" in result
