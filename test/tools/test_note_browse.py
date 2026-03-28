"""Tests for list_folder and view_folder_structure."""

from macllm.tools.note import list_folder, view_folder_structure
from macllm.tags.file_tag import FileTag


class TestListFolder:
    def test_list_root_folder(self, file_env):
        result = list_folder(str(file_env))

        assert "alpha.md" in result
        assert "beta.txt" in result
        assert "gamma.md" not in result  # nested in subdir

    def test_list_subfolder(self, file_env):
        result = list_folder(str(file_env / "subdir"))

        assert "gamma.md" in result
        assert "alpha.md" not in result

    def test_list_empty_folder(self, file_env):
        empty_dir = file_env / "empty_dir"
        empty_dir.mkdir()

        result = list_folder(str(empty_dir))
        assert "No indexed notes" in result

    def test_list_rejects_outside_indexed(self, file_env):
        result = list_folder("/tmp/not-indexed")
        assert "Error" in result
        assert "not within an indexed folder" in result

    def test_list_rejects_file_path(self, file_env):
        result = list_folder(str(file_env / "alpha.md"))
        assert "Error" in result
        assert "Not a folder" in result


class TestViewFolderStructure:
    def test_shows_all_notes(self, file_env):
        result = view_folder_structure()

        assert "alpha.md" in result
        assert "beta.txt" in result
        assert "gamma.md" in result

    def test_shows_folder_hierarchy(self, file_env):
        result = view_folder_structure()

        assert str(file_env) + "/" in result
        assert "subdir/" in result

    def test_no_indexed_folders(self, file_env):
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
