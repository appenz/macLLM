import pytest
from unittest.mock import patch, MagicMock

from macllm.tools.file_search import search_files, read_full_file
from macllm.tags.file_tag import FileTag


class DummyArgs:
    debug = False


class DummyApp:
    args = DummyArgs()

    def debug_log(self, *args, **kwargs):
        pass

    def debug_exception(self, *args, **kwargs):
        pass


@pytest.fixture
def file_tag_with_index(tmp_path):
    test_file1 = tmp_path / "doc1.md"
    test_file1.write_text("This is document one about Python programming.")
    test_file2 = tmp_path / "doc2.md"
    test_file2.write_text("This is document two about JavaScript frameworks.")

    FileTag._macllm = DummyApp()
    FileTag._index = [
        ("doc1.md", str(test_file1)),
        ("doc2.md", str(test_file2)),
    ]
    FileTag._embedding_ready.set()

    mock_embeddings = MagicMock()
    mock_embeddings.search.return_value = [(0, 0.95), (1, 0.80)]
    FileTag._embeddings = mock_embeddings

    yield tmp_path

    FileTag._index = []
    FileTag._embeddings = None
    FileTag._embedding_ready.clear()


def test_search_files_returns_formatted_results(file_tag_with_index):
    result = search_files("Python programming")

    assert "[File ID: 0]" in result
    assert "[File ID: 1]" in result
    assert "doc1.md" in result
    assert "Score:" in result
    assert "Python programming" in result
    assert "(complete)" in result  # short files are not truncated


def test_search_files_no_results(file_tag_with_index):
    FileTag._embeddings.search.return_value = []
    result = search_files("nonexistent topic")
    assert "No matching files found" in result


def test_read_full_file_returns_content(file_tag_with_index):
    result = read_full_file(0)

    assert "doc1.md" in result
    assert "Python programming" in result


def test_read_full_file_invalid_id(file_tag_with_index):
    result = read_full_file(999)
    assert "Error" in result


def test_read_full_file_truncates_long_content(tmp_path):
    long_file = tmp_path / "long.md"
    long_content = "x" * 20000
    long_file.write_text(long_content)

    FileTag._index = [("long.md", str(long_file))]

    result = read_full_file(0)

    content_part = result.split("\n\n", 1)[1] if "\n\n" in result else result
    assert len(content_part) <= 10000

    FileTag._index = []


def test_search_files_shows_truncated_indicator(tmp_path):
    long_file = tmp_path / "long.md"
    long_content = "x" * 2000  # longer than SEARCH_PREVIEW_LEN (1000)
    long_file.write_text(long_content)

    FileTag._macllm = DummyApp()
    FileTag._index = [("long.md", str(long_file))]
    FileTag._embedding_ready.set()

    mock_embeddings = MagicMock()
    mock_embeddings.search.return_value = [(0, 0.9)]
    FileTag._embeddings = mock_embeddings

    result = search_files("test")
    assert "(truncated)" in result

    FileTag._index = []
    FileTag._embeddings = None
    FileTag._embedding_ready.clear()
