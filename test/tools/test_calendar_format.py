"""Unit tests for calendar event text formatting (no EventKit / real calendar)."""

from datetime import datetime, timezone

from maccal.types import Event, Participant, ParticipantStatus

from macllm.tools.calendar import _format_event, _format_participant_rsvp


def _sample_event(**kwargs):
    start = datetime(2026, 4, 1, 10, 0, tzinfo=timezone.utc)
    end = datetime(2026, 4, 1, 11, 0, tzinfo=timezone.utc)
    defaults = dict(
        event_id="e1",
        title="Sync",
        start=start,
        end=end,
        is_all_day=False,
        calendar="Work",
        calendar_id="cid",
    )
    defaults.update(kwargs)
    return Event(**defaults)


def test_format_event_includes_rsvp_per_line():
    ev = _sample_event(
        attendees=[
            Participant(
                name="Ann",
                email="ann@example.com",
                status=ParticipantStatus.ACCEPTED,
            ),
            Participant(
                name="Ben",
                email="ben@example.com",
                status=ParticipantStatus.PENDING,
            ),
        ]
    )
    text = _format_event(ev)
    assert "  Attendees:" in text
    assert "Ann (ann@example.com) — accepted" in text
    assert "Ben (ben@example.com) — no response" in text


def test_format_participant_rsvp_variants():
    assert _format_participant_rsvp(Participant(status=ParticipantStatus.DECLINED)) == "declined"
    assert _format_participant_rsvp(Participant(status=ParticipantStatus.TENTATIVE)) == "tentative"
    assert _format_participant_rsvp(Participant(status=ParticipantStatus.UNKNOWN)) == "unknown"
