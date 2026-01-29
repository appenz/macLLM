import threading
import pytest
from unittest.mock import patch, MagicMock

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
def file_tag_with_files(tmp_path):
    doc1 = tmp_path / "doc1.md"
    doc1.write_text("Document about machine learning and neural networks.")
    doc2 = tmp_path / "doc2.md"
    doc2.write_text("Document about web development and JavaScript.")
    doc3 = tmp_path / "doc3.txt"
    doc3.write_text("Plain text document about databases and SQL.")

    tag = FileTag(DummyApp())
    tag.on_config_tag("@IndexFiles", str(tmp_path))
    FileTag.build_index()

    yield tag, tmp_path

    FileTag._index = []
    FileTag._indexed_directories = []
    FileTag._embeddings = None
    FileTag._embedding_ready = threading.Event()


def test_index_populated_after_config_tag(file_tag_with_files):
    tag, _ = file_tag_with_files
    assert len(FileTag._index) == 3
    filenames = [name for name, _ in FileTag._index]
    assert "doc1.md" in filenames
    assert "doc2.md" in filenames
    assert "doc3.txt" in filenames


def test_embedding_not_ready_initially(file_tag_with_files):
    tag, _ = file_tag_with_files
    assert not FileTag._embedding_ready.is_set()


def test_build_embeddings_sets_ready_flag(file_tag_with_files):
    tag, _ = file_tag_with_files

    mock_embeddings = MagicMock()
    with patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag._build_embeddings()

    assert FileTag._embedding_ready.is_set()
    assert FileTag._embeddings is mock_embeddings
    mock_embeddings.index.assert_called_once()


def test_start_embedding_build_spawns_thread(file_tag_with_files):
    tag, _ = file_tag_with_files

    mock_embeddings = MagicMock()
    with patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag.start_embedding_build()
        FileTag._embedding_ready.wait(timeout=5.0)

    assert FileTag._embedding_ready.is_set()


def test_search_returns_results(file_tag_with_files):
    tag, _ = file_tag_with_files

    mock_embeddings = MagicMock()
    mock_embeddings.search.return_value = [(0, 0.9), (2, 0.7)]
    FileTag._embeddings = mock_embeddings
    FileTag._embedding_ready.set()

    results = FileTag.search("machine learning")
    assert len(results) == 2
    assert results[0][0] == 0
    assert results[0][1] == 0.9
    assert "doc1.md" in results[0][2]
    assert "machine learning" in results[0][3]
    assert results[0][4] is False  # not truncated (short file)


def test_search_waits_for_embedding_ready(file_tag_with_files):
    tag, _ = file_tag_with_files
    FileTag._embedding_ready.clear()

    mock_embeddings = MagicMock()
    mock_embeddings.search.return_value = []
    FileTag._embeddings = mock_embeddings

    def set_ready_after_delay():
        import time
        time.sleep(0.1)
        FileTag._embedding_ready.set()

    threading.Thread(target=set_ready_after_delay, daemon=True).start()
    results = FileTag.search("test", timeout=2.0)
    assert results == []


def test_search_timeout_returns_empty(file_tag_with_files):
    tag, _ = file_tag_with_files
    FileTag._embedding_ready.clear()

    results = FileTag.search("test", timeout=0.01)
    assert results == []


def test_get_file_content_returns_content(file_tag_with_files):
    tag, _ = file_tag_with_files
    content, path = FileTag.get_file_content(0)
    assert "doc1.md" in path
    assert len(content) > 0


def test_get_file_content_invalid_id(file_tag_with_files):
    tag, _ = file_tag_with_files
    with pytest.raises(IndexError):
        FileTag.get_file_content(999)


def test_reindex_clears_ready_flag(file_tag_with_files):
    tag, _ = file_tag_with_files
    FileTag._embedding_ready.set()

    with patch.object(FileTag, "start_embedding_build"):
        FileTag._start_reindex()

    assert not FileTag._embedding_ready.is_set()


def test_expand_reindex_triggers_rebuild(file_tag_with_files):
    tag, _ = file_tag_with_files
    FileTag._embedding_ready.set()

    with patch.object(FileTag, "start_embedding_build") as mock_build:
        result = tag.expand("/reindex", None, None)

    assert result == ""
    mock_build.assert_called_once()
    assert not FileTag._embedding_ready.is_set()


def test_get_prefixes_includes_reindex(file_tag_with_files):
    tag, _ = file_tag_with_files
    prefixes = tag.get_prefixes()
    assert "/reindex" in prefixes


def test_get_file_content_truncates_long_files(tmp_path):
    long_file = tmp_path / "long.md"
    long_content = "a" * 20000
    long_file.write_text(long_content)

    FileTag._index = [("long.md", str(long_file))]

    content, _ = FileTag.get_file_content(0)
    assert len(content) == 10000

    FileTag._index = []
