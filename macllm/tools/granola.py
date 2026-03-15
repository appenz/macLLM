"""Granola tools wrapping the libgranola library for reading meeting notes."""

import time

from smolagents import tool

_tool_call_counter = {
    "granola_list_meetings": 0,
    "granola_find_meetings": 0,
    "granola_get_meeting": 0,
    "granola_get_transcript": 0,
    "granola_list_people": 0,
}

_store_singleton = None


def _get_store():
    """Lazy-initialize a singleton GranolaStore."""
    global _store_singleton
    if _store_singleton is None:
        from libgranola import GranolaStore

        _store_singleton = GranolaStore()
    return _store_singleton


def _status_manager():
    from macllm.macllm import MacLLM

    return MacLLM.get_status_manager()


def _make_tool_id(name: str) -> str:
    _tool_call_counter[name] += 1
    return f"{name}_{_tool_call_counter[name]}_{int(time.time() * 1000)}"


def _parse_csv(value: str | None) -> list[str] | None:
    """Split a comma-separated string into a list, or return None."""
    if not value:
        return None
    return [s.strip() for s in value.split(",") if s.strip()]


def _short_id(full_id: str) -> str:
    """Return the last 6 characters of a UUID as a compact identifier."""
    return full_id[-6:]


def _resolve_id(store, short_or_full: str) -> str:
    """Resolve a short (6-char suffix) or full meeting ID to the full UUID.

    Raises ValueError if the ID is ambiguous or not found.
    """
    if store.get_meeting(short_or_full) is not None:
        return short_or_full
    matches = [
        m for m in store.list_meetings(include_invalid=True)
        if m.id.endswith(short_or_full)
    ]
    if len(matches) == 1:
        return matches[0].id
    if len(matches) > 1:
        raise ValueError(
            f"Ambiguous ID '{short_or_full}' matches {len(matches)} meetings. "
            "Use a longer ID."
        )
    raise ValueError(f"No meeting found with ID '{short_or_full}'.")


def _pad(text: str, width: int) -> str:
    """Truncate with '...' if needed, then pad to exactly *width* characters.

    Pipe characters are escaped so they don't break markdown table structure.
    """
    text = text.replace("|", "\\|")
    if len(text) <= width:
        return text.ljust(width)
    return text[: width - 3] + "..."


# Column widths for the meetings table (total row width = 80).
_COL_ID = 6
_COL_DATE = 10
_COL_TITLE = 25
_COL_ATT = 26


def _format_meetings_table(meetings: list, total: int | None = None) -> str:
    """Format meetings as a fixed-width 80-char markdown table."""
    header = (
        f"| {_pad('ID', _COL_ID)} "
        f"| {_pad('Date', _COL_DATE)} "
        f"| {_pad('Title', _COL_TITLE)} "
        f"| {_pad('Attendees', _COL_ATT)} |"
    )
    sep = (
        f"|{'-' * (_COL_ID + 2)}"
        f"|{'-' * (_COL_DATE + 2)}"
        f"|{'-' * (_COL_TITLE + 2)}"
        f"|{'-' * (_COL_ATT + 2)}|"
    )
    rows: list[str] = []
    for m in meetings:
        names = [a.name or a.email or "?" for a in m.attendees]
        row = (
            f"| {_pad(_short_id(m.id), _COL_ID)} "
            f"| {_pad(m.created_at.strftime('%Y-%m-%d'), _COL_DATE)} "
            f"| {_pad(m.title, _COL_TITLE)} "
            f"| {_pad(', '.join(names), _COL_ATT)} |"
        )
        rows.append(row)

    total_count = total if total is not None else len(meetings)
    count_line = f"Showing {len(meetings)} of {total_count} meetings:"
    return "\n".join([count_line, "", header, sep] + rows)


def _format_meeting_detail(m) -> str:
    """Full detail view for a single meeting."""
    date_fmt = "%Y-%m-%d %H:%M"
    lines = [
        f"Title: {m.title}",
        f"ID: {m.id}",
        f"Created: {m.created_at.strftime(date_fmt)}",
    ]
    if m.updated_at:
        lines.append(f"Updated: {m.updated_at.strftime(date_fmt)}")
    if m.creator:
        creator_parts = [m.creator.name or "", m.creator.email or ""]
        lines.append(f"Creator: {' '.join(p for p in creator_parts if p)}")
    if m.attendees:
        lines.append("Attendees:")
        for a in m.attendees:
            parts = []
            if a.name:
                parts.append(a.name)
            if a.email:
                parts.append(f"<{a.email}>")
            if a.company:
                parts.append(f"({a.company})")
            if a.job_title:
                parts.append(f"- {a.job_title}")
            lines.append(f"  - {' '.join(parts)}")
    if m.calendar_event:
        ev = m.calendar_event
        if ev.start and ev.end:
            lines.append(
                f"Calendar event: {ev.start.strftime(date_fmt)} – "
                f"{ev.end.strftime(date_fmt)}"
            )
        if ev.location:
            lines.append(f"Location: {ev.location}")
    if m.overview:
        lines.append(f"\nOverview:\n{m.overview}")
    if m.summary:
        lines.append(f"\nSummary:\n{m.summary}")
    if m.notes_markdown:
        lines.append(f"\nNotes:\n{m.notes_markdown}")
    elif m.notes_plain:
        lines.append(f"\nNotes:\n{m.notes_plain}")
    return "\n".join(lines)


def _format_person(p) -> str:
    """Format a Person for the people list."""
    parts = [p.name]
    if p.email:
        parts.append(f"<{p.email}>")
    if p.company_name:
        parts.append(f"({p.company_name})")
    if p.job_title:
        parts.append(f"- {p.job_title}")
    return "- " + " ".join(parts)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@tool
def granola_list_meetings(limit: int = 50) -> str:
    """
    List Granola meeting notes, newest first.

    Args:
        limit: Maximum number of meetings to return. Defaults to 50.

    Returns:
        A markdown table of meetings showing short ID, date, title, and attendees.
    """
    tool_id = _make_tool_id("granola_list_meetings")
    status = _status_manager()
    status.start_tool_call(tool_id, "granola_list_meetings", {"limit": limit})

    try:
        store = _get_store()
        meetings = store.list_meetings()
        if not meetings:
            status.complete_tool_call(tool_id, "0 meetings")
            return "No Granola meetings found."
        shown = meetings[:limit]
        result = _format_meetings_table(shown, total=len(meetings))
        status.complete_tool_call(tool_id, f"{len(shown)} meetings")
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
def granola_find_meetings(query: str, fields: str = "") -> str:
    """
    Search Granola meeting notes by text. Case-insensitive.

    Args:
        query: The text to search for across meeting content.
        fields: Optional comma-separated field names to restrict the search. Valid fields: title, notes_plain, notes_markdown, overview, summary, attendee_name, attendee_email, creator_name, creator_email. Leave empty to search all fields.

    Returns:
        A formatted list of matching meetings, or a message if none found.
    """
    tool_id = _make_tool_id("granola_find_meetings")
    status = _status_manager()
    status.start_tool_call(tool_id, "granola_find_meetings", {"query": query})

    try:
        store = _get_store()
        field_list = _parse_csv(fields)
        meetings = store.find_meetings(query, fields=field_list)
        if not meetings:
            status.complete_tool_call(tool_id, "0 matches")
            return f"No meetings matching '{query}' found."
        result = _format_meetings_table(meetings)
        status.complete_tool_call(tool_id, f"{len(meetings)} matches")
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
def granola_get_meeting(meeting_id: str) -> str:
    """
    Get full details of a Granola meeting including notes, attendees, and summary.

    Args:
        meeting_id: The meeting ID -- either the 6-character short ID from the meeting list or the full UUID.

    Returns:
        Full meeting details including title, date, attendees, notes, overview, and summary.
    """
    tool_id = _make_tool_id("granola_get_meeting")
    status = _status_manager()
    status.start_tool_call(tool_id, "granola_get_meeting", {"id": meeting_id})

    try:
        store = _get_store()
        try:
            full_id = _resolve_id(store, meeting_id)
        except ValueError as e:
            status.complete_tool_call(tool_id, "not found")
            return str(e)
        meeting = store.get_meeting(full_id)
        result = _format_meeting_detail(meeting)
        status.complete_tool_call(tool_id, meeting.title[:30])
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
def granola_get_transcript(meeting_id: str) -> str:
    """
    Get the transcript for a Granola meeting as timestamped segments.

    Args:
        meeting_id: The meeting ID -- either the 6-character short ID from the meeting list or the full UUID.

    Returns:
        The meeting transcript with timestamps, or a message if unavailable.
    """
    tool_id = _make_tool_id("granola_get_transcript")
    status = _status_manager()
    status.start_tool_call(tool_id, "granola_get_transcript", {"id": meeting_id})

    try:
        store = _get_store()
        try:
            full_id = _resolve_id(store, meeting_id)
        except ValueError as e:
            status.complete_tool_call(tool_id, "not found")
            return str(e)
        segments = store.get_transcript(full_id)
        if segments is None:
            status.complete_tool_call(tool_id, "no transcript")
            return f"No transcript available for meeting '{meeting_id}'."
        if not segments:
            status.complete_tool_call(tool_id, "empty transcript")
            return f"Transcript for meeting '{meeting_id}' is empty."
        lines = [
            f"[{seg.start:%H:%M:%S}] {seg.text}"
            for seg in segments
        ]
        result = "\n".join(lines)
        status.complete_tool_call(tool_id, f"{len(segments)} segments")
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
def granola_list_people() -> str:
    """
    List the people directory from Granola, showing contacts from past meetings.

    Returns:
        A formatted list of people with name, email, company, and job title.
    """
    tool_id = _make_tool_id("granola_list_people")
    status = _status_manager()
    status.start_tool_call(tool_id, "granola_list_people", {})

    try:
        store = _get_store()
        people = store.list_people()
        if not people:
            status.complete_tool_call(tool_id, "0 people")
            return "No people found in Granola directory."
        lines = [_format_person(p) for p in people]
        result = f"{len(people)} contacts:\n\n" + "\n".join(lines)
        status.complete_tool_call(tool_id, f"{len(people)} people")
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise
