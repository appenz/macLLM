"""External tests for the note subagent with real LLM calls.

These tests create a temporary notes directory, index it, and run the
NoteAgent (and DefaultAgent) against real LLM APIs.

Run with: make test-external
"""

import os
import time

import pytest

from macllm.tags.file_tag import FileTag
from macllm.core.agent_status import AgentStatusManager
from macllm.core.agent_service import create_agent


class DummyApp:
    class _Args:
        debug = False

    args = _Args()

    def __init__(self):
        self.status_manager = AgentStatusManager()

    def debug_log(self, *a, **kw):
        pass

    def debug_exception(self, *a, **kw):
        pass


@pytest.fixture
def notes_env(tmp_path):
    """Create a temporary notes directory with test files and configure FileTag."""
    from macllm.macllm import MacLLM

    notes = tmp_path / "notes"
    notes.mkdir()

    (notes / "travel-plans.md").write_text(
        "# Travel Plans\n\n"
        "Trip to Tokyo scheduled for March 2026.\n"
        "Hotel: Park Hyatt Tokyo\n"
        "Flight: JAL 005 from SFO\n"
    )
    (notes / "recipes.md").write_text(
        "# Favorite Recipes\n\n"
        "## Pasta Carbonara\n"
        "Eggs, pecorino, guanciale, black pepper.\n"
    )
    (notes / "contacts.md").write_text(
        "# Contacts\n\n"
        "Alice: alice@example.com\n"
        "Bob: 555-0123\n"
    )

    dummy = DummyApp()
    FileTag._macllm = dummy
    MacLLM._instance = dummy
    FileTag._indexed_directories = [str(notes)]

    FileTag.build_index()
    FileTag._build_embeddings()

    yield notes

    FileTag._index = []
    FileTag._indexed_directories = []
    FileTag._filepath_to_idx = {}
    FileTag._embeddings = None
    FileTag._embedding_ready.clear()
    FileTag._file_mtimes = {}
    FileTag._first_build_done = False
    FileTag._macllm = None
    MacLLM._instance = None


def _skip_if_no_gemini():
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")


@pytest.mark.external
def test_note_agent_search(notes_env):
    """NoteAgent can find a note by semantic search."""
    _skip_if_no_gemini()

    from macllm.agents.note_agent import NoteAgent
    agent = create_agent(agent_cls=NoteAgent, speed="normal")
    result = agent.run(
        "Search for the user's travel plans and tell me the hotel name.",
        max_steps=5,
    )

    assert "Park Hyatt" in result


@pytest.mark.external
def test_note_agent_read(notes_env):
    """NoteAgent can read a specific note and extract information."""
    _skip_if_no_gemini()

    from macllm.agents.note_agent import NoteAgent
    agent = create_agent(agent_cls=NoteAgent, speed="normal")
    result = agent.run(
        "Find Bob's phone number from the user's notes.",
        max_steps=5,
    )

    assert "555-0123" in result


@pytest.mark.external
def test_note_agent_creates_note(notes_env):
    """NoteAgent can create a new note."""
    _skip_if_no_gemini()

    from macllm.agents.note_agent import NoteAgent
    agent = create_agent(agent_cls=NoteAgent, speed="normal")
    result = agent.run(
        f"Create a new note at {notes_env}/shopping-list.md with the content:\n"
        "# Shopping List\n- Milk\n- Eggs\n- Bread",
        max_steps=5,
    )

    assert "Successfully created" in result or "shopping-list" in result.lower()
    created = notes_env / "shopping-list.md"
    assert created.exists()
    content = created.read_text()
    assert "Milk" in content


@pytest.mark.external
def test_note_agent_appends(notes_env):
    """NoteAgent can append to an existing note found by search."""
    _skip_if_no_gemini()

    from macllm.agents.note_agent import NoteAgent
    agent = create_agent(agent_cls=NoteAgent, speed="normal")
    result = agent.run(
        "Find the recipes file and append a new recipe:\n"
        "## Scrambled Eggs\nEggs, butter, salt.",
        max_steps=5,
    )

    content = (notes_env / "recipes.md").read_text()
    assert "Scrambled Eggs" in content


@pytest.mark.external
def test_default_agent_delegates_note_task(notes_env):
    """DefaultAgent delegates a note question to the notes subagent."""
    _skip_if_no_gemini()

    from macllm.agents.default import MacLLMDefaultAgent
    agent = create_agent(agent_cls=MacLLMDefaultAgent, speed="normal")
    result = agent.run(
        "What hotel am I staying at in Tokyo? Check my notes.",
        max_steps=10,
    )

    assert "Park Hyatt" in result
