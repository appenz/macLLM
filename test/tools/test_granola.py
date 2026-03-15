"""Granola tool tests with mocked GranolaStore.

All tests mock the libgranola store so they run without a real Granola
installation. Integration tests that hit the real cache are marked with
@pytest.mark.granola and run via ``make test-granola``.
"""

from datetime import datetime
from unittest.mock import patch, MagicMock

import pytest

from macllm.core.agent_status import AgentStatusManager


class DummyApp:
    """Minimal stand-in for MacLLM so status reporting works inside tools."""

    class _Args:
        debug = False

    args = _Args()

    def __init__(self):
        self.status_manager = AgentStatusManager()

    def debug_log(self, *a, **kw):
        pass

    def debug_exception(self, *a, **kw):
        pass


@pytest.fixture(autouse=True)
def _patch_macllm():
    """Wire up a DummyApp so status reporting works inside tools."""
    from macllm.macllm import MacLLM

    MacLLM._instance = DummyApp()
    yield
    MacLLM._instance = None


@pytest.fixture(autouse=True)
def _reset_store():
    """Reset the singleton store between tests."""
    import macllm.tools.granola as mod

    mod._store_singleton = None
    yield
    mod._store_singleton = None


def _make_meeting(id="d313e3d7-6e93-401d-a340-4dbecd033e2a", title="Standup",
                  attendees=None, **kwargs):
    from libgranola import Meeting, Attendee

    defaults = dict(
        id=id,
        title=title,
        created_at=datetime(2026, 3, 10, 9, 0),
        attendees=attendees or [
            Attendee(name="Alice", email="alice@example.com"),
            Attendee(name="Bob", email="bob@example.com"),
        ],
    )
    defaults.update(kwargs)
    return Meeting(**defaults)


def _make_person(id="p1", name="Alice", **kwargs):
    from libgranola import Person

    defaults = dict(id=id, name=name)
    defaults.update(kwargs)
    return Person(**defaults)


def _make_segment(id="s1", text="Hello everyone", **kwargs):
    from libgranola import TranscriptSegment

    defaults = dict(
        id=id,
        document_id="m1",
        start=datetime(2026, 3, 10, 9, 0, 0),
        end=datetime(2026, 3, 10, 9, 0, 5),
        text=text,
    )
    defaults.update(kwargs)
    return TranscriptSegment(**defaults)


def _mock_store(**overrides):
    """Create a MagicMock GranolaStore with sensible defaults."""
    store = MagicMock()
    store.list_meetings.return_value = overrides.get("meetings", [])
    store.find_meetings.return_value = overrides.get("found", [])
    store.get_meeting.return_value = overrides.get("meeting", None)
    store.get_transcript.return_value = overrides.get("transcript", None)
    store.list_people.return_value = overrides.get("people", [])
    return store


# ---------------------------------------------------------------------------
# Short ID helpers
# ---------------------------------------------------------------------------

class TestShortId:
    def test_returns_last_6(self):
        from macllm.tools.granola import _short_id

        assert _short_id("d313e3d7-6e93-401d-a340-4dbecd033e2a") == "033e2a"

    def test_short_string(self):
        from macllm.tools.granola import _short_id

        assert _short_id("abc123") == "abc123"


class TestResolveId:
    def test_exact_match(self):
        from macllm.tools.granola import _resolve_id

        full = "d313e3d7-6e93-401d-a340-4dbecd033e2a"
        meeting = _make_meeting(id=full)
        store = _mock_store(meetings=[meeting])
        store.get_meeting.side_effect = lambda mid: meeting if mid == full else None

        assert _resolve_id(store, full) == full

    def test_short_suffix_match(self):
        from macllm.tools.granola import _resolve_id

        full = "d313e3d7-6e93-401d-a340-4dbecd033e2a"
        meeting = _make_meeting(id=full)
        store = _mock_store(meetings=[meeting])
        store.get_meeting.return_value = None
        store.list_meetings.return_value = [meeting]

        assert _resolve_id(store, "033e2a") == full

    def test_ambiguous_raises(self):
        from macllm.tools.granola import _resolve_id

        m1 = _make_meeting(id="aaaa-033e2a")
        m2 = _make_meeting(id="bbbb-033e2a")
        store = _mock_store()
        store.get_meeting.return_value = None
        store.list_meetings.return_value = [m1, m2]

        with pytest.raises(ValueError, match="Ambiguous"):
            _resolve_id(store, "033e2a")

    def test_not_found_raises(self):
        from macllm.tools.granola import _resolve_id

        store = _mock_store()
        store.get_meeting.return_value = None
        store.list_meetings.return_value = []

        with pytest.raises(ValueError, match="No meeting found"):
            _resolve_id(store, "xxxxxx")


# ---------------------------------------------------------------------------
# Table formatter
# ---------------------------------------------------------------------------

class TestFormatMeetingsTable:
    def test_table_width(self):
        from macllm.tools.granola import _format_meetings_table

        meetings = [_make_meeting(), _make_meeting(
            id="e95df488-94b7-4d7e-9e6f-7be24d78ace8", title="Retro",
        )]
        result = _format_meetings_table(meetings)
        lines = result.split("\n")
        for line in lines[2:]:  # skip the count line and blank line
            assert len(line) == 80, f"Line is {len(line)} chars: {line!r}"

    def test_contains_data(self):
        from macllm.tools.granola import _format_meetings_table

        meetings = [_make_meeting()]
        result = _format_meetings_table(meetings)

        assert "033e2a" in result
        assert "2026-03-10" in result
        assert "Standup" in result
        assert "Alice" in result

    def test_truncates_long_title(self):
        from macllm.tools.granola import _format_meetings_table

        meetings = [_make_meeting(title="A Very Long Meeting Title That Exceeds The Column")]
        result = _format_meetings_table(meetings)

        assert "..." in result
        lines = result.split("\n")
        for line in lines[2:]:
            assert len(line) == 80

    def test_total_count(self):
        from macllm.tools.granola import _format_meetings_table

        meetings = [_make_meeting()]
        result = _format_meetings_table(meetings, total=42)

        assert "1 of 42" in result

    def test_header_row(self):
        from macllm.tools.granola import _format_meetings_table

        meetings = [_make_meeting()]
        result = _format_meetings_table(meetings)

        assert "| ID" in result
        assert "| Date" in result
        assert "| Title" in result
        assert "| Attendees" in result


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

class TestGranolaListMeetings:
    def test_returns_table(self):
        meetings = [_make_meeting(), _make_meeting(
            id="e95df488-94b7-4d7e-9e6f-7be24d78ace8", title="Retro",
        )]
        with patch("macllm.tools.granola._get_store", return_value=_mock_store(meetings=meetings)):
            from macllm.tools.granola import granola_list_meetings

            result = granola_list_meetings()

        assert "Standup" in result
        assert "Retro" in result
        assert "2026-03-10" in result
        assert "Alice" in result
        assert "033e2a" in result
        assert "| ID" in result

    def test_empty(self):
        with patch("macllm.tools.granola._get_store", return_value=_mock_store()):
            from macllm.tools.granola import granola_list_meetings

            result = granola_list_meetings()

        assert "No Granola meetings found" in result

    def test_limit(self):
        meetings = [
            _make_meeting(id=f"d313e3d7-6e93-401d-a340-{i:012d}", title=f"Meeting {i}")
            for i in range(10)
        ]
        with patch("macllm.tools.granola._get_store", return_value=_mock_store(meetings=meetings)):
            from macllm.tools.granola import granola_list_meetings

            result = granola_list_meetings(limit=3)

        assert "3 of 10" in result


class TestGranolaFindMeetings:
    def test_finds_matching(self):
        found = [_make_meeting()]
        with patch("macllm.tools.granola._get_store", return_value=_mock_store(found=found)):
            from macllm.tools.granola import granola_find_meetings

            result = granola_find_meetings("standup")

        assert "Standup" in result
        assert "1 of 1" in result

    def test_no_matches(self):
        with patch("macllm.tools.granola._get_store", return_value=_mock_store()):
            from macllm.tools.granola import granola_find_meetings

            result = granola_find_meetings("nonexistent")

        assert "No meetings matching" in result

    def test_fields_passed(self):
        store = _mock_store()
        with patch("macllm.tools.granola._get_store", return_value=store):
            from macllm.tools.granola import granola_find_meetings

            granola_find_meetings("alice", fields="attendee_name,attendee_email")

        store.find_meetings.assert_called_once_with(
            "alice", fields=["attendee_name", "attendee_email"]
        )


class TestGranolaGetMeeting:
    def test_returns_detail(self):
        full_id = "d313e3d7-6e93-401d-a340-4dbecd033e2a"
        meeting = _make_meeting(
            id=full_id,
            overview="Weekly sync overview",
            summary="Discussed roadmap",
            notes_markdown="# Notes\n- item 1",
        )
        store = _mock_store(meetings=[meeting])
        store.get_meeting.side_effect = lambda mid: meeting if mid == full_id else None
        store.list_meetings.return_value = [meeting]

        with patch("macllm.tools.granola._get_store", return_value=store):
            from macllm.tools.granola import granola_get_meeting

            result = granola_get_meeting("033e2a")

        assert "Standup" in result
        assert "Weekly sync overview" in result
        assert "Discussed roadmap" in result
        assert "# Notes" in result
        assert "Alice" in result

    def test_not_found(self):
        store = _mock_store()
        store.get_meeting.return_value = None
        store.list_meetings.return_value = []

        with patch("macllm.tools.granola._get_store", return_value=store):
            from macllm.tools.granola import granola_get_meeting

            result = granola_get_meeting("nonexistent")

        assert "No meeting found" in result


class TestGranolaGetTranscript:
    def test_returns_segments(self):
        full_id = "d313e3d7-6e93-401d-a340-4dbecd033e2a"
        meeting = _make_meeting(id=full_id)
        segments = [
            _make_segment(id="s1", text="Hello everyone"),
            _make_segment(id="s2", text="Let's start",
                          start=datetime(2026, 3, 10, 9, 0, 10),
                          end=datetime(2026, 3, 10, 9, 0, 15)),
        ]
        store = _mock_store(transcript=segments, meetings=[meeting])
        store.get_meeting.side_effect = lambda mid: meeting if mid == full_id else None
        store.list_meetings.return_value = [meeting]

        with patch("macllm.tools.granola._get_store", return_value=store):
            from macllm.tools.granola import granola_get_transcript

            result = granola_get_transcript("033e2a")

        assert "09:00:00" in result
        assert "Hello everyone" in result
        assert "Let's start" in result

    def test_no_transcript(self):
        full_id = "d313e3d7-6e93-401d-a340-4dbecd033e2a"
        meeting = _make_meeting(id=full_id)
        store = _mock_store(meetings=[meeting])
        store.get_meeting.side_effect = lambda mid: meeting if mid == full_id else None
        store.list_meetings.return_value = [meeting]

        with patch("macllm.tools.granola._get_store", return_value=store):
            from macllm.tools.granola import granola_get_transcript

            result = granola_get_transcript("033e2a")

        assert "No transcript available" in result

    def test_empty_transcript(self):
        full_id = "d313e3d7-6e93-401d-a340-4dbecd033e2a"
        meeting = _make_meeting(id=full_id)
        store = _mock_store(transcript=[], meetings=[meeting])
        store.get_meeting.side_effect = lambda mid: meeting if mid == full_id else None
        store.list_meetings.return_value = [meeting]

        with patch("macllm.tools.granola._get_store", return_value=store):
            from macllm.tools.granola import granola_get_transcript

            result = granola_get_transcript("033e2a")

        assert "empty" in result

    def test_not_found(self):
        store = _mock_store()
        store.get_meeting.return_value = None
        store.list_meetings.return_value = []

        with patch("macllm.tools.granola._get_store", return_value=store):
            from macllm.tools.granola import granola_get_transcript

            result = granola_get_transcript("xxxxxx")

        assert "No meeting found" in result


class TestGranolaListPeople:
    def test_returns_people(self):
        people = [
            _make_person(name="Alice", email="alice@example.com",
                         company_name="Acme", job_title="Engineer"),
            _make_person(id="p2", name="Bob"),
        ]
        with patch("macllm.tools.granola._get_store", return_value=_mock_store(people=people)):
            from macllm.tools.granola import granola_list_people

            result = granola_list_people()

        assert "Alice" in result
        assert "alice@example.com" in result
        assert "Acme" in result
        assert "Engineer" in result
        assert "Bob" in result
        assert "2 contacts" in result

    def test_empty(self):
        with patch("macllm.tools.granola._get_store", return_value=_mock_store()):
            from macllm.tools.granola import granola_list_people

            result = granola_list_people()

        assert "No people found" in result


# ---------------------------------------------------------------------------
# Fast-path __call__ override
# ---------------------------------------------------------------------------

class TestGranolaAgentFastPath:
    def test_list_all_returns_table(self):
        meetings = [_make_meeting()]
        store = _mock_store(meetings=meetings)

        with patch("macllm.tools.granola._get_store", return_value=store):
            from macllm.agents.granola_agent import GranolaAgent

            agent = GranolaAgent.__new__(GranolaAgent)
            result = agent._try_fast_path("LIST_ALL")

        assert result is not None
        assert "| ID" in result
        assert "Standup" in result
        assert "033e2a" in result

    def test_list_all_empty(self):
        store = _mock_store()

        with patch("macllm.tools.granola._get_store", return_value=store):
            from macllm.agents.granola_agent import GranolaAgent

            agent = GranolaAgent.__new__(GranolaAgent)
            result = agent._try_fast_path("LIST_ALL")

        assert "No Granola meetings found" in result

    def test_other_task_returns_none(self):
        from macllm.agents.granola_agent import GranolaAgent

        agent = GranolaAgent.__new__(GranolaAgent)
        result = agent._try_fast_path("Find meetings about product roadmap")

        assert result is None
