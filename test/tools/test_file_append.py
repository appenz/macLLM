import pytest
import os

from macllm.tools.file_append import file_append, file_create, _resolve_file_path
from macllm.tags.file_tag import FileTag
from macllm.core.agent_status import AgentStatusManager


class DummyArgs:
    debug = False


class DummyConversation:
    def __init__(self):
        self.context_history = []

    def has_path_in_context(self, path: str) -> bool:
        for ctx in self.context_history:
            if ctx.get("type") == "path" and ctx.get("source") == path:
                return True
        return False


class DummyApp:
    args = DummyArgs()

    def __init__(self):
        self.chat_history = DummyConversation()
        self.status_manager = AgentStatusManager()

    def debug_log(self, *args, **kwargs):
        pass

    def debug_exception(self, *args, **kwargs):
        pass

    def check_path_in_active_conversations(self, path: str) -> bool:
        return self.chat_history.has_path_in_context(path)


@pytest.fixture
def setup_file_tag(tmp_path):
    """Set up FileTag with indexed directory and files."""
    from macllm.macllm import MacLLM
    
    test_file = tmp_path / "existing.md"
    test_file.write_text("Original content")

    dummy_app = DummyApp()
    FileTag._macllm = dummy_app
    MacLLM._instance = dummy_app  # For status manager access
    FileTag._indexed_directories = [str(tmp_path)]
    FileTag._index = [("existing.md", str(test_file))]

    yield tmp_path

    # Cleanup
    FileTag._index = []
    FileTag._indexed_directories = []
    FileTag._macllm = None
    MacLLM._instance = None


# ===== file_append tests =====

def test_append_to_existing_file_by_id(setup_file_tag):
    """Test appending to an existing file using its ID."""
    result = file_append("0", "New content")

    assert "Successfully appended to" in result
    filepath = FileTag._index[0][1]
    content = open(filepath).read()
    assert "Original content\nNew content" in content


def test_append_fails_on_nonexistent_file(setup_file_tag):
    """Test that file_append fails if file doesn't exist."""
    result = file_append("new-note.md", "Content")

    assert "Error" in result
    assert "does not exist" in result


def test_append_newline_handling(setup_file_tag):
    """Test that newlines are added correctly when appending."""
    file_append("0", "First append")
    file_append("0", "Second append")

    filepath = FileTag._index[0][1]
    content = open(filepath).read()
    assert "Original content\nFirst append\nSecond append" in content


# ===== file_create tests =====

def test_create_new_file_with_filename(setup_file_tag):
    """Test creating a new file with just a filename."""
    result = file_create("new-note.md", "Brand new content")

    assert "Successfully created" in result
    new_path = os.path.join(setup_file_tag, "new-note.md")
    assert os.path.exists(new_path)
    assert open(new_path).read() == "Brand new content"


def test_create_fails_on_existing_file(setup_file_tag):
    """Test that file_create fails if file already exists."""
    result = file_create("0", "Content")

    assert "Error" in result
    assert "already exists" in result


def test_create_adds_md_extension(setup_file_tag):
    """Test that .md extension is auto-added if missing."""
    result = file_create("auto-extension", "Content here")

    assert "Successfully created" in result
    new_path = os.path.join(setup_file_tag, "auto-extension.md")
    assert os.path.exists(new_path)


def test_create_adds_to_index(setup_file_tag):
    """Test that newly created files are added to the index."""
    file_create("indexed-file.md", "Content")

    assert any("indexed-file.md" in fp for _, fp in FileTag._index)


# ===== shared behavior tests =====

def test_reject_arbitrary_path(setup_file_tag):
    """Test that arbitrary paths are rejected."""
    arbitrary_path = "/tmp/macllm-test-not-indexed/random.md"

    assert "Error" in file_append(arbitrary_path, "Fail")
    assert "Error" in file_create(arbitrary_path, "Fail")


def test_reject_invalid_file_id(setup_file_tag):
    """Test that invalid file IDs are rejected."""
    assert "Error" in file_append("999", "Fail")
    assert "Error" in file_create("999", "Fail")


def test_user_referenced_path(setup_file_tag, tmp_path):
    """Test writing to a path the user explicitly referenced."""
    external_dir = tmp_path / "external"
    external_dir.mkdir()
    external_file = external_dir / "referenced.md"
    external_file.write_text("External content")

    FileTag._macllm.chat_history.context_history.append({
        "type": "path",
        "source": str(external_file),
        "name": "referenced.md"
    })

    result = file_append(str(external_file), "Appended")
    assert "Successfully appended to" in result


def test_resolve_file_path_numeric_id(setup_file_tag):
    """Test _resolve_file_path with numeric ID."""
    assert _resolve_file_path("0") == FileTag._index[0][1]
    assert _resolve_file_path("999") is None


def test_resolve_file_path_filename(setup_file_tag):
    """Test _resolve_file_path with plain filename."""
    result = _resolve_file_path("newfile.md")
    expected = os.path.join(FileTag._indexed_directories[0], "newfile.md")
    assert result == expected
