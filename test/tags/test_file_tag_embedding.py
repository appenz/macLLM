import json
import os
import time
import threading
import pytest
from unittest.mock import patch, MagicMock, call

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
    FileTag._reindex_event = threading.Event()
    FileTag._file_mtimes = {}
    FileTag._filepath_to_idx = {}
    FileTag._first_build_done = False


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


def test_build_embeddings_sets_ready_flag(file_tag_with_files, tmp_path):
    tag, _ = file_tag_with_files
    no_cache = tmp_path / "no_cache"

    mock_embeddings = MagicMock()
    with patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings), \
         patch.object(FileTag, "_cache_dir", return_value=no_cache):
        FileTag._build_embeddings()

    assert FileTag._embedding_ready.is_set()
    assert FileTag._embeddings is mock_embeddings
    mock_embeddings.index.assert_called_once()


def test_start_index_loop_builds_embeddings(file_tag_with_files):
    tag, _ = file_tag_with_files

    mock_embeddings = MagicMock()
    with patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag.start_index_loop(interval=9999)
        FileTag._embedding_ready.wait(timeout=5.0)

    assert FileTag._embedding_ready.is_set()


def test_search_returns_results(file_tag_with_files):
    tag, _ = file_tag_with_files

    fp0 = FileTag._index[0][1]
    fp2 = FileTag._index[2][1]

    mock_embeddings = MagicMock()
    mock_embeddings.search.return_value = [(fp0, 0.9), (fp2, 0.7)]
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


def test_reindex_sets_event(file_tag_with_files):
    tag, _ = file_tag_with_files
    FileTag._reindex_event.clear()

    FileTag._start_reindex()

    assert FileTag._reindex_event.is_set()


def test_expand_reindex_triggers_rebuild(file_tag_with_files):
    tag, _ = file_tag_with_files
    FileTag._reindex_event.clear()

    result = tag.expand("/reindex", None, None)

    assert result == ""
    assert FileTag._reindex_event.is_set()


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


def test_first_build_calls_index(file_tag_with_files, tmp_path):
    """First _build_embeddings call should use index(), not upsert()."""
    tag, _ = file_tag_with_files
    no_cache = tmp_path / "no_cache"

    mock_embeddings = MagicMock()
    with patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings), \
         patch.object(FileTag, "_cache_dir", return_value=no_cache):
        FileTag._build_embeddings()

    mock_embeddings.index.assert_called_once()
    mock_embeddings.upsert.assert_not_called()
    assert FileTag._first_build_done is True
    assert len(FileTag._file_mtimes) == 3


def test_skip_when_nothing_changed(file_tag_with_files):
    """Second build with no file changes should skip entirely."""
    tag, _ = file_tag_with_files

    mock_embeddings = MagicMock()
    with patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag._build_embeddings()
        mock_embeddings.reset_mock()
        FileTag._build_embeddings()

    mock_embeddings.index.assert_not_called()
    mock_embeddings.upsert.assert_not_called()
    mock_embeddings.delete.assert_not_called()


def test_upsert_on_changed_file(file_tag_with_files):
    """Modifying a file should trigger upsert() on the next build."""
    tag, tmp_path = file_tag_with_files

    mock_embeddings = MagicMock()
    with patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag._build_embeddings()
        mock_embeddings.reset_mock()

        doc1 = tmp_path / "doc1.md"
        time.sleep(0.05)
        doc1.write_text("Updated content about deep learning.")

        FileTag.build_index()
        FileTag._build_embeddings()

    mock_embeddings.upsert.assert_called_once()
    upserted_docs = mock_embeddings.upsert.call_args[0][0]
    assert len(upserted_docs) == 1
    assert upserted_docs[0][0] == str(doc1)


def test_upsert_on_new_file(file_tag_with_files):
    """Adding a new file should trigger upsert() on the next build."""
    tag, tmp_path = file_tag_with_files

    mock_embeddings = MagicMock()
    with patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag._build_embeddings()
        mock_embeddings.reset_mock()

        new_file = tmp_path / "doc4.md"
        new_file.write_text("Brand new document.")

        FileTag.build_index()
        FileTag._build_embeddings()

    mock_embeddings.upsert.assert_called_once()
    upserted_docs = mock_embeddings.upsert.call_args[0][0]
    assert len(upserted_docs) == 1
    assert upserted_docs[0][0] == str(new_file)


def test_delete_on_removed_file(file_tag_with_files):
    """Removing a file should trigger delete() on the next build."""
    tag, tmp_path = file_tag_with_files

    mock_embeddings = MagicMock()
    with patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag._build_embeddings()
        mock_embeddings.reset_mock()

        doc3 = tmp_path / "doc3.txt"
        removed_path = str(doc3)
        os.remove(doc3)

        FileTag.build_index()
        FileTag._build_embeddings()

    mock_embeddings.delete.assert_called_once()
    deleted_ids = mock_embeddings.delete.call_args[0][0]
    assert removed_path in deleted_ids


def test_filepath_to_idx_populated(file_tag_with_files):
    """build_index() should populate _filepath_to_idx."""
    tag, tmp_path = file_tag_with_files
    assert len(FileTag._filepath_to_idx) == 3
    for _, filepath in FileTag._index:
        assert filepath in FileTag._filepath_to_idx


# ------------------------------------------------------------------
# Disk persistence tests
# ------------------------------------------------------------------

def test_save_cache_creates_files(file_tag_with_files, tmp_path):
    """_save_cache() should write mtimes.json and call embeddings.save()."""
    tag, _ = file_tag_with_files
    cache_dir = tmp_path / "cache"

    mock_embeddings = MagicMock()
    with patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings), \
         patch.object(FileTag, "_cache_dir", return_value=cache_dir):
        FileTag._build_embeddings()

    assert (cache_dir / "mtimes.json").exists()
    with open(cache_dir / "mtimes.json") as f:
        saved_mtimes = json.load(f)
    assert len(saved_mtimes) == 3
    mock_embeddings.save.assert_called_once_with(str(cache_dir))


def test_load_cache_restores_state(file_tag_with_files, tmp_path):
    """_load_cache() should restore _file_mtimes and _embeddings from disk."""
    tag, _ = file_tag_with_files
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    fake_mtimes = {fp: 1000.0 for _, fp in FileTag._index}
    with open(cache_dir / "mtimes.json", "w") as f:
        json.dump(fake_mtimes, f)

    mock_embeddings = MagicMock()
    with patch.object(FileTag, "_cache_dir", return_value=cache_dir), \
         patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        result = FileTag._load_cache()

    assert result is True
    assert FileTag._first_build_done is True
    assert FileTag._file_mtimes == fake_mtimes
    assert FileTag._embeddings is mock_embeddings
    mock_embeddings.load.assert_called_once_with(str(cache_dir))


def test_cold_start_with_cache_skips_full_index(file_tag_with_files, tmp_path):
    """When a valid cache exists, first build should use upsert, not index."""
    tag, _ = file_tag_with_files
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    current_mtimes = {}
    for _, fp in FileTag._index:
        current_mtimes[fp] = os.path.getmtime(fp)
    with open(cache_dir / "mtimes.json", "w") as f:
        json.dump(current_mtimes, f)

    mock_embeddings = MagicMock()
    with patch.object(FileTag, "_cache_dir", return_value=cache_dir), \
         patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag._build_embeddings()

    mock_embeddings.load.assert_called_once()
    mock_embeddings.index.assert_not_called()
    mock_embeddings.upsert.assert_not_called()
    assert FileTag._embedding_ready.is_set()


def test_cold_start_with_stale_cache_upserts_changed(file_tag_with_files, tmp_path):
    """Cache with outdated mtimes should trigger upsert for changed files."""
    tag, data_dir = file_tag_with_files
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    stale_mtimes = {}
    for _, fp in FileTag._index:
        stale_mtimes[fp] = os.path.getmtime(fp)
    doc1_path = str(data_dir / "doc1.md")
    stale_mtimes[doc1_path] = 0.0
    with open(cache_dir / "mtimes.json", "w") as f:
        json.dump(stale_mtimes, f)

    mock_embeddings = MagicMock()
    with patch.object(FileTag, "_cache_dir", return_value=cache_dir), \
         patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag._build_embeddings()

    mock_embeddings.load.assert_called_once()
    mock_embeddings.index.assert_not_called()
    mock_embeddings.upsert.assert_called_once()
    upserted = mock_embeddings.upsert.call_args[0][0]
    assert len(upserted) == 1
    assert upserted[0][0] == doc1_path


def test_corrupted_cache_falls_back_to_full_index(file_tag_with_files, tmp_path):
    """A corrupted cache should be ignored and a full index() should run."""
    tag, _ = file_tag_with_files
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()

    with open(cache_dir / "mtimes.json", "w") as f:
        f.write("NOT VALID JSON{{{")

    mock_embeddings = MagicMock()
    with patch.object(FileTag, "_cache_dir", return_value=cache_dir), \
         patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag._build_embeddings()

    mock_embeddings.index.assert_called_once()
    assert FileTag._embedding_ready.is_set()


def test_no_cache_on_disk_does_full_index(file_tag_with_files, tmp_path):
    """When no cache exists, first build should do a full index()."""
    tag, _ = file_tag_with_files
    cache_dir = tmp_path / "nonexistent_cache"

    mock_embeddings = MagicMock()
    with patch.object(FileTag, "_cache_dir", return_value=cache_dir), \
         patch("macllm.tags.file_tag.txtai.Embeddings", return_value=mock_embeddings):
        FileTag._build_embeddings()

    mock_embeddings.index.assert_called_once()
    assert FileTag._first_build_done is True
