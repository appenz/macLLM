"""Tests for list_folder, find_folder, and view_folder_structure (mount-path API)."""

from macllm.tools.note import list_folder, find_folder, view_folder_structure
from macllm.tags.file_tag import FileTag

from .conftest import MOUNT_NAME


class TestListFolder:
    def test_list_root_folder(self, file_env):
        result = list_folder(MOUNT_NAME)

        assert "alpha.md" in result
        assert "beta.txt" in result
        assert "gamma.md" not in result  # nested in subdir

    def test_list_shows_subdirectories(self, file_env):
        result = list_folder(MOUNT_NAME)
        assert "subdir/" in result

    def test_list_subfolder(self, file_env):
        result = list_folder(f"{MOUNT_NAME}/subdir")

        assert "gamma.md" in result
        assert "alpha.md" not in result

    def test_list_empty_folder(self, file_env):
        empty_dir = file_env / "empty_dir"
        empty_dir.mkdir()

        result = list_folder(f"{MOUNT_NAME}/empty_dir")
        assert "No indexed notes or subfolders" in result

    def test_list_shows_empty_subfolder(self, file_env):
        (file_env / "empty_sub").mkdir()
        result = list_folder(MOUNT_NAME)
        assert "empty_sub/" in result

    def test_list_rejects_outside_indexed(self, file_env):
        result = list_folder("/tmp/not-indexed")
        assert "Error" in result
        assert "not within an indexed folder" in result

    def test_list_rejects_file_path(self, file_env):
        result = list_folder(f"{MOUNT_NAME}/alpha.md")
        assert "Error" in result
        assert "Not a folder" in result

    def test_list_shows_mount_path_in_header(self, file_env):
        result = list_folder(MOUNT_NAME)
        assert f"Folder: {MOUNT_NAME}" in result

    def test_list_hides_hidden_directories(self, file_env):
        (file_env / ".hidden").mkdir()
        result = list_folder(MOUNT_NAME)
        assert ".hidden" not in result


class TestFindFolder:
    def test_finds_subfolder_by_name(self, file_env):
        result = find_folder("subdir")
        assert f"{MOUNT_NAME}/subdir" in result

    def test_case_insensitive(self, file_env):
        result = find_folder("SUBDIR")
        assert f"{MOUNT_NAME}/subdir" in result

    def test_substring_match(self, file_env):
        result = find_folder("sub")
        assert f"{MOUNT_NAME}/subdir" in result

    def test_matches_mount_name(self, file_env):
        result = find_folder("Note")
        assert MOUNT_NAME in result

    def test_no_matches(self, file_env):
        result = find_folder("zzz-nonexistent")
        assert "No matching folders found" in result

    def test_finds_empty_folder(self, file_env):
        (file_env / "empty_target").mkdir()
        result = find_folder("empty_target")
        assert f"{MOUNT_NAME}/empty_target" in result

    def test_finds_nested_folder(self, file_env):
        nested = file_env / "subdir" / "deep"
        nested.mkdir()
        result = find_folder("deep")
        assert f"{MOUNT_NAME}/subdir/deep" in result

    def test_skips_hidden_folders(self, file_env):
        (file_env / ".hidden_dir").mkdir()
        result = find_folder("hidden_dir")
        assert "No matching folders found" in result


class TestViewFolderStructure:
    def test_shows_all_notes(self, file_env):
        result = view_folder_structure()

        assert "alpha.md" in result
        assert "beta.txt" in result
        assert "gamma.md" in result

    def test_shows_mount_name_as_root(self, file_env):
        result = view_folder_structure()
        assert f"{MOUNT_NAME}/" in result

    def test_shows_folder_hierarchy(self, file_env):
        result = view_folder_structure()

        assert f"{MOUNT_NAME}/" in result
        assert "subdir/" in result

    def test_no_indexed_folders(self, file_env):
        FileTag._mount_points = {}
        FileTag._indexed_directories = []
        FileTag._index = []

        result = view_folder_structure()
        assert "No folders" in result

    def test_shows_note_count_in_status(self, file_env):
        from macllm.macllm import MacLLM
        view_folder_structure()

        status = MacLLM.get_status_manager()
        last = status.tool_calls[-1]
        assert "3 notes" in last.result_summary
