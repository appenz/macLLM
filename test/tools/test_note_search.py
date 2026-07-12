"""Tests for semantic note search over indexed filesystem mounts."""

from unittest.mock import MagicMock

from macllm.core.chat_history import Conversation
from macllm.core.context import set_current_conversation
from macllm.tags.file_tag import FileTag
from macllm.tools.filesystem import read_file
from macllm.tools.note import search_notes

from .conftest import MOUNT_VIRTUAL


class TestSearchNotes:
    def test_returns_virtual_paths_and_scores(self, file_env):
        mock_emb = MagicMock()
        mock_emb.search.return_value = [(0, 0.95), (1, 0.80)]
        FileTag._embeddings = mock_emb
        FileTag._embedding_ready.set()

        result = search_notes("travel")

        assert f"{MOUNT_VIRTUAL}/alpha.md" in result
        assert f"{MOUNT_VIRTUAL}/beta.txt" in result
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

        result = search_notes("nonexistent")
        assert "No matching notes found" in result

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

        result = search_notes("test")
        assert "(truncated)" in result

        FileTag._embeddings = None
        FileTag._embedding_ready.clear()

    def test_no_file_ids_in_output(self, file_env):
        mock_emb = MagicMock()
        mock_emb.search.return_value = [(0, 0.95)]
        FileTag._embeddings = mock_emb
        FileTag._embedding_ready.set()

        result = search_notes("travel")
        assert "[File ID:" not in result

        FileTag._embeddings = None
        FileTag._embedding_ready.clear()

    def test_search_path_can_be_read_directly(self, file_env):
        conversation = Conversation()
        set_current_conversation(conversation)
        try:
            result = read_file.forward(f"{MOUNT_VIRTUAL}/alpha.md")
        finally:
            set_current_conversation(None)

        assert result == "Alpha content about travel"
