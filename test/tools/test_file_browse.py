"""Tests for list_directory and view_directory_structure."""

from macllm.tools.file_browse import list_directory, view_directory_structure
from macllm.tags.file_tag import FileTag


class TestListDirectory:
    def test_list_root_directory(self, file_env):
        result = list_directory(str(file_env))

        assert "alpha.md" in result
        assert "beta.txt" in result
        assert "gamma.md" not in result  # nested in subdir

    def test_list_subdirectory(self, file_env):
        result = list_directory(str(file_env / "subdir"))

        assert "gamma.md" in result
        assert "alpha.md" not in result

    def test_list_empty_directory(self, file_env):
        empty_dir = file_env / "empty_dir"
        empty_dir.mkdir()

        result = list_directory(str(empty_dir))
        assert "No indexed files" in result

    def test_list_rejects_outside_indexed(self, file_env):
        result = list_directory("/tmp/not-indexed")
        assert "Error" in result
        assert "not within an indexed directory" in result

    def test_list_rejects_file_path(self, file_env):
        result = list_directory(str(file_env / "alpha.md"))
        assert "Error" in result
        assert "Not a directory" in result


class TestViewDirectoryStructure:
    def test_shows_all_files(self, file_env):
        result = view_directory_structure()

        assert "alpha.md" in result
        assert "beta.txt" in result
        assert "gamma.md" in result

    def test_shows_directory_hierarchy(self, file_env):
        result = view_directory_structure()

        assert str(file_env) + "/" in result
        assert "subdir/" in result

    def test_no_indexed_directories(self, file_env):
        FileTag._indexed_directories = []
        FileTag._index = []

        result = view_directory_structure()
        assert "No directories" in result

    def test_shows_file_count_in_status(self, file_env):
        from macllm.macllm import MacLLM
        view_directory_structure()

        status = MacLLM.get_status_manager()
        last = status.tool_calls[-1]
        assert "3 files" in last.result_summary
