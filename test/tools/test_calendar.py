"""Calendar tool tests against the real macOS calendar.

Run with: make test-calendar

All tests create events with a unique prefix and clean them up afterwards
so the user's calendar is not polluted.
"""

import uuid
from datetime import datetime, timedelta

import pytest

from macllm.core.agent_status import AgentStatusManager

# AppKit needs a shared NSApplication for NSColor operations used by maccal
from AppKit import NSApplication
NSApplication.sharedApplication()

TEST_PREFIX = f"__macllm_test_{uuid.uuid4().hex[:8]}"


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


@pytest.fixture(autouse=True)
def _patch_macllm():
    """Wire up a DummyApp so status reporting works inside tools."""
    from macllm.macllm import MacLLM

    MacLLM._instance = DummyApp()
    yield
    MacLLM._instance = None


@pytest.fixture()
def store():
    """Provide a CalendarStore for direct cleanup operations."""
    from maccal import CalendarStore

    return CalendarStore()


@pytest.fixture()
def cleanup(store):
    """Collect event IDs during a test and delete them on teardown."""
    event_ids: list[str] = []
    yield event_ids
    for eid in event_ids:
        try:
            store.delete_event(eid)
        except Exception:
            pass


def _future_range():
    """Return start/end strings for a window 30-31 days from now (unlikely to have real events)."""
    base = datetime.now() + timedelta(days=30)
    start = base.replace(hour=8, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=10)
    fmt = "%Y-%m-%d %H:%M"
    return start.strftime(fmt), end.strftime(fmt)


def _event_start_end():
    """Return start/end strings for a single 1-hour event 30 days from now."""
    base = datetime.now() + timedelta(days=30)
    start = base.replace(hour=14, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=1)
    fmt = "%Y-%m-%d %H:%M"
    return start.strftime(fmt), end.strftime(fmt)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.calendar
@pytest.mark.skip(
    reason="maccal's NSColor.colorWithCGColor_ Bus-errors without a full Cocoa app context"
)
def test_list_calendars():
    from macllm.tools.calendar import cal_list_calendars

    result = cal_list_calendars()
    assert isinstance(result, str)
    assert len(result) > 0
    assert "type=" in result


@pytest.mark.calendar
def test_add_and_find_event(cleanup):
    from macllm.tools.calendar import cal_add_event, cal_find_events

    title = f"{TEST_PREFIX}_add_find"
    start, end = _event_start_end()

    result = cal_add_event(title=title, start=start, end=end)
    assert "Event created" in result
    assert title in result

    # Extract event_id from result for cleanup
    for line in result.splitlines():
        if line.strip().startswith("ID:"):
            eid = line.strip().split("ID:")[1].strip()
            cleanup.append(eid)
            break

    range_start, range_end = _future_range()
    found = cal_find_events(query=title, start=range_start, end=range_end)
    assert title in found


@pytest.mark.calendar
def test_get_events(cleanup):
    from macllm.tools.calendar import cal_add_event, cal_get_events

    title = f"{TEST_PREFIX}_get"
    start, end = _event_start_end()

    add_result = cal_add_event(title=title, start=start, end=end)
    for line in add_result.splitlines():
        if line.strip().startswith("ID:"):
            cleanup.append(line.strip().split("ID:")[1].strip())
            break

    range_start, range_end = _future_range()
    result = cal_get_events(start=range_start, end=range_end)
    assert title in result


@pytest.mark.calendar
def test_update_event(cleanup):
    from macllm.tools.calendar import cal_add_event, cal_update_event

    original_title = f"{TEST_PREFIX}_update_orig"
    updated_title = f"{TEST_PREFIX}_update_new"
    start, end = _event_start_end()

    add_result = cal_add_event(title=original_title, start=start, end=end)
    event_id = None
    for line in add_result.splitlines():
        if line.strip().startswith("ID:"):
            event_id = line.strip().split("ID:")[1].strip()
            cleanup.append(event_id)
            break

    assert event_id is not None

    update_result = cal_update_event(event_id=event_id, title=updated_title)
    assert "Event updated" in update_result
    assert updated_title in update_result


@pytest.mark.calendar
def test_find_free_time():
    from macllm.tools.calendar import cal_find_free_time

    base = datetime.now() + timedelta(days=60)
    start = base.replace(hour=6, minute=0, second=0, microsecond=0)
    end = start + timedelta(hours=12)
    fmt = "%Y-%m-%d %H:%M"

    result = cal_find_free_time(
        start=start.strftime(fmt),
        end=end.strftime(fmt),
        duration_minutes=30,
    )
    assert isinstance(result, str)
    # 60 days out should have free time
    assert "–" in result or "No free time" in result


@pytest.mark.calendar
def test_timezone_parsing(cleanup):
    from zoneinfo import ZoneInfo

    from macllm.tools.calendar import cal_add_event, cal_find_events

    title = f"{TEST_PREFIX}_tz"
    base = datetime.now(tz=ZoneInfo("America/New_York")) + timedelta(days=30)
    start_dt = base.replace(hour=17, minute=0, second=0, microsecond=0)
    end_dt = start_dt + timedelta(hours=1)
    fmt = "%Y-%m-%d %H:%M"
    start_str = start_dt.strftime(fmt)
    end_str = end_dt.strftime(fmt)

    result = cal_add_event(
        title=title,
        start=start_str,
        end=end_str,
        timezone="America/New_York",
    )
    assert "Event created" in result

    for line in result.splitlines():
        if line.strip().startswith("ID:"):
            cleanup.append(line.strip().split("ID:")[1].strip())
            break

    range_start = (start_dt - timedelta(hours=2)).strftime(fmt)
    range_end = (end_dt + timedelta(hours=2)).strftime(fmt)
    found = cal_find_events(query=title, start=range_start, end=range_end)
    assert title in found
