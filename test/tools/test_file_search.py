"""Tests for search_files and read_file (path-based API)."""

from unittest.mock import MagicMock
from pathlib import Path

from macllm.tools.file import search_files, read_file
from macllm.tags.file_tag import FileTag


class TestSearchFiles:
    def test_returns_paths_and_scores(self, file_env):
        mock_emb = MagicMock()
        mock_emb.search.return_value = [(0, 0.95), (1, 0.80)]
        FileTag._embeddings = mock_emb
        FileTag._embedding_ready.set()

        result = search_files("travel")

        assert str(file_env / "alpha.md") in result
        assert str(file_env / "beta.txt") in result
        assert "Score: 0.950" in result
        assert "Score: 0.800" in result
        assert "Alpha content" in result

        FileTag._embeddings = None
        FileTag._embedding_ready.clear()

    def test_no_results(self, file_env):
        mock_emb = MagicMock()
        mock_emb.search.return_value = []
        FileTag._embeddings = mock_emb
        FileTag._embedding_ready.set()

        result = search_files("nonexistent")
        assert "No matching files found" in result

        FileTag._embeddings = None
        FileTag._embedding_ready.clear()

    def test_truncated_indicator(self, file_env):
        long_file = file_env / "long.md"
        long_file.write_text("x" * 2000)
        FileTag._index.append(("long.md", str(long_file)))
        FileTag._filepath_to_idx[str(long_file)] = 3

        mock_emb = MagicMock()
        mock_emb.search.return_value = [(str(long_file), 0.9)]
        FileTag._embeddings = mock_emb
        FileTag._embedding_ready.set()

        result = search_files("test")
        assert "(truncated)" in result

        FileTag._embeddings = None
        FileTag._embedding_ready.clear()

    def test_no_file_ids_in_output(self, file_env):
        mock_emb = MagicMock()
        mock_emb.search.return_value = [(0, 0.95)]
        FileTag._embeddings = mock_emb
        FileTag._embedding_ready.set()

        result = search_files("travel")
        assert "[File ID:" not in result

        FileTag._embeddings = None
        FileTag._embedding_ready.clear()


class TestReadFile:
    def test_read_existing_file(self, file_env):
        result = read_file(str(file_env / "alpha.md"))

        assert "alpha.md" in result
        assert "Alpha content about travel" in result

    def test_read_nested_file(self, file_env):
        result = read_file(str(file_env / "subdir" / "gamma.md"))

        assert "gamma.md" in result
        assert "Gamma nested content" in result

    def test_rejects_path_outside_indexed_dirs(self, file_env):
        result = read_file("/tmp/not-indexed/secret.md")
        assert "Error" in result
        assert "not within an indexed directory" in result

    def test_rejects_nonexistent_file(self, file_env):
        result = read_file(str(file_env / "nonexistent.md"))
        assert "Error" in result
        assert "not found" in result

    def test_truncates_long_file(self, file_env):
        long_file = file_env / "long.md"
        long_file.write_text("x" * 20000)
        FileTag._index.append(("long.md", str(long_file)))

        result = read_file(str(long_file))
        content_part = result.split("\n\n", 1)[1]
        assert len(content_part) <= FileTag.MAX_FULL_FILE_LEN
