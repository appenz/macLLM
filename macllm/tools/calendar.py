"""Calendar tools wrapping the maccal library for macOS EventKit access."""

import hashlib
import re
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from macllm.tools._debug import macllm_tool, set_tool_message

_store_singleton = None


def _get_store():
    """Lazy-initialize a singleton CalendarStore."""
    global _store_singleton
    if _store_singleton is None:
        from maccal import CalendarStore

        _store_singleton = CalendarStore()
    return _store_singleton


def _local_tz() -> ZoneInfo:
    """Return the system local timezone."""
    return datetime.now().astimezone().tzinfo


def _parse_datetime(dt_str: str, timezone: str | None = None) -> datetime:
    """Parse a datetime string and attach timezone info.

    Accepts 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD'. If timezone is an IANA name
    (e.g. 'Europe/Berlin'), the parsed time is interpreted in that zone.
    Otherwise the system local timezone is used.
    """
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(dt_str.strip(), fmt)
            break
        except ValueError:
            continue
    else:
        raise ValueError(
            f"Cannot parse '{dt_str}'. Use format YYYY-MM-DD HH:MM or YYYY-MM-DD."
        )

    tz = ZoneInfo(timezone) if timezone else _local_tz()
    return dt.replace(tzinfo=tz)


def _parse_csv(value: str | None) -> list[str] | None:
    """Split a comma-separated string into a list, or return None."""
    if not value:
        return None
    return [s.strip() for s in value.split(",") if s.strip()]


def _attendee_label(participant) -> str:
    """Display name and email for a single participant, if available."""
    name, email = participant.name, participant.email
    if name and email and name.strip() != email.strip():
        return f"{name} ({email})"
    if name or email:
        return (name or email or "").strip() or "unknown"
    return "unknown"


def _format_participant_rsvp(participant) -> str:
    """Map maccal ParticipantStatus to a short, human-readable RSVP label."""
    from maccal import ParticipantStatus

    st = getattr(participant, "status", None)
    if st is None or st == ParticipantStatus.UNKNOWN:
        return "unknown"
    labels = {
        ParticipantStatus.PENDING: "no response",
        ParticipantStatus.ACCEPTED: "accepted",
        ParticipantStatus.DECLINED: "declined",
        ParticipantStatus.TENTATIVE: "tentative",
        ParticipantStatus.DELEGATED: "delegated",
        ParticipantStatus.COMPLETED: "completed",
        ParticipantStatus.IN_PROCESS: "in process",
    }
    if st in labels:
        return labels[st]
    return getattr(st, "name", str(st)).replace("_", " ").lower()


def _format_event(ev) -> str:
    """Format a maccal Event into a readable block."""
    time_fmt = "%Y-%m-%d %H:%M"
    if ev.is_all_day:
        when = f"{ev.start.strftime('%Y-%m-%d')} (all day)"
    else:
        when = f"{ev.start.strftime(time_fmt)} – {ev.end.strftime(time_fmt)}"
        if ev.time_zone:
            when += f" ({ev.time_zone})"

    lines = [
        f"- {ev.title} (Calendar: {ev.calendar})",
        f"  ID: {ev.event_id}",
        f"  When: {when}",
    ]
    if ev.location:
        lines.append(f"  Location: {ev.location}")
    if ev.notes:
        lines.append(f"  Notes: {ev.notes}")
    if ev.url:
        lines.append(f"  URL: {ev.url}")
    if ev.attendees:
        lines.append("  Attendees:")
        for a in ev.attendees:
            who = _attendee_label(a)
            rsvp = _format_participant_rsvp(a)
            lines.append(f"    {who} — {rsvp}")
    if ev.is_recurring:
        lines.append("  Recurring: yes")
    if ev.availability and ev.availability.name != "NOT_SUPPORTED":
        lines.append(f"  Availability: {ev.availability.name.lower()}")
    return "\n".join(lines)


def _format_time_slot(slot) -> str:
    fmt = "%Y-%m-%d %H:%M"
    mins = int(slot.duration.total_seconds() // 60)
    return f"- {slot.start.strftime(fmt)} – {slot.end.strftime(fmt)} ({mins} min)"


# ---------------------------------------------------------------------------
# Short event IDs — stateless, format: YYYY-MM-DD-<4 hex>
# ---------------------------------------------------------------------------

_SHORT_ID_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})-([0-9a-f]{4})$")
_MAX_SUMMARY_ATTENDEES = 5


def _short_event_id(ev) -> str:
    """Produce a compact ID from an event: ``<UTC-date>-<4 hex hash>``."""
    utc_date = ev.start.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%d")
    h = hashlib.sha256(ev.event_id.encode()).hexdigest()[:4]
    return f"{utc_date}-{h}"


def _resolve_event(short_or_full_id: str):
    """Resolve a short ID to its maccal Event, or search by full ID.

    Returns the matching Event object.  Raises ValueError on no match.
    """
    store = _get_store()
    m = _SHORT_ID_RE.match(short_or_full_id)
    if m:
        date_str, hash_prefix = m.group(1), m.group(2)
        day_start = _parse_datetime(date_str, "UTC")
        day_end = day_start + timedelta(days=1)
        events = store.get_events(day_start, day_end)
        for ev in events:
            if hashlib.sha256(ev.event_id.encode()).hexdigest()[:4] == hash_prefix:
                return ev
        raise ValueError(
            f"No event found matching short ID '{short_or_full_id}'."
        )
    # Full ID — search a wide window and match by event_id
    now = datetime.now().astimezone()
    window_start = now - timedelta(days=365)
    window_end = now + timedelta(days=365)
    events = store.get_events(window_start, window_end)
    for ev in events:
        if ev.event_id == short_or_full_id:
            return ev
    raise ValueError(f"No event found with ID '{short_or_full_id}'.")


def _format_event_summary(ev) -> str:
    """Compact event format for search/list results."""
    time_fmt = "%Y-%m-%d %H:%M"
    if ev.is_all_day:
        when = f"{ev.start.strftime('%Y-%m-%d')} (all day)"
    else:
        when = f"{ev.start.strftime(time_fmt)} – {ev.end.strftime(time_fmt)}"
        if ev.time_zone:
            when += f" ({ev.time_zone})"

    lines = [
        f"- {ev.title}",
        f"  Calendar: {ev.calendar}",
        f"  ID: {_short_event_id(ev)}",
        f"  When: {when}",
    ]
    if ev.location:
        loc = ev.location if len(ev.location) <= 80 else ev.location[:77] + "..."
        lines.append(f"  Location: {loc}")
    if ev.attendees:
        lines.append("  Attendees:")
        shown = ev.attendees[:_MAX_SUMMARY_ATTENDEES]
        for a in shown:
            who = _attendee_label(a)
            rsvp = _format_participant_rsvp(a)
            lines.append(f"    {who} — {rsvp}")
        remaining = len(ev.attendees) - len(shown)
        if remaining > 0:
            lines.append(f"    (+{remaining} more)")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@macllm_tool
def cal_list_calendars() -> str:
    """
    List all available macOS calendars.

    Returns:
        A formatted list of calendars showing name, type, and source.
    """
    set_tool_message("Listing calendars")
    store = _get_store()
    cals = store.list_calendars()
    if not cals:
        return "No calendars found."
    lines = []
    for c in cals:
        parts = [c.title, f"type={c.type.name.lower()}"]
        if c.source:
            parts.append(f"source={c.source}")
        lines.append("- " + ", ".join(parts))
    return "\n".join(lines)


@macllm_tool
def cal_get_events(start: str, end: str, calendars: str = "") -> str:
    """
    Fetch all calendar events in a date range.

    Args:
        start: Start of range in 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' format.
        end: End of range in 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' format.
        calendars: Optional comma-separated list of calendar names to filter by. Leave empty for all calendars.

    Returns:
        A formatted list of events in the date range.
    """
    set_tool_message(f"Loading events {start} → {end}")
    store = _get_store()
    dt_start = _parse_datetime(start)
    dt_end = _parse_datetime(end)
    cal_list = _parse_csv(calendars)
    events = store.get_events(dt_start, dt_end, calendars=cal_list)
    if not events:
        return "No events found in this range."
    return "\n\n".join(_format_event_summary(ev) for ev in events)


@macllm_tool
def cal_find_events(
    query: str, start: str, end: str, calendars: str = "", fields: str = ""
) -> str:
    """
    Search calendar events by text. Searches across event titles, locations, notes, attendees, and more.

    Args:
        query: The text to search for (case-insensitive).
        start: Start of search range in 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' format.
        end: End of search range in 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' format.
        calendars: Optional comma-separated calendar names to restrict search. Leave empty for all.
        fields: Optional comma-separated field names to search. Valid fields: title, location, notes, url, calendar, organizer_name, organizer_email, attendee_name, attendee_email. Leave empty to search all fields.

    Returns:
        A formatted list of matching events, or a message if none found.
    """
    set_tool_message(f'Searching calendar for "{query}"')
    store = _get_store()
    dt_start = _parse_datetime(start)
    dt_end = _parse_datetime(end)
    cal_list = _parse_csv(calendars)
    field_list = _parse_csv(fields)
    events = store.find_events(
        query,
        start=dt_start,
        end=dt_end,
        calendars=cal_list,
        fields=field_list,
    )
    if not events:
        return f"No events matching '{query}' found in this range."
    return "\n\n".join(_format_event_summary(ev) for ev in events)


@macllm_tool
def cal_get_event(event_id: str) -> str:
    """
    Get full details of a calendar event by its ID.

    Use this to retrieve complete information (notes, all attendees, URLs)
    for an event found via cal_get_events or cal_find_events.

    Args:
        event_id: The event ID (short or full, from a previous search or listing).

    Returns:
        Complete event details including notes, all attendees with RSVP, and URL.
    """
    set_tool_message(f"Loading event {event_id}")
    ev = _resolve_event(event_id)
    return _format_event(ev)


@macllm_tool
def cal_add_event(
    title: str,
    start: str,
    end: str,
    calendar: str = "",
    location: str = "",
    notes: str = "",
    is_all_day: bool = False,
    timezone: str = "",
) -> str:
    """
    Create a new calendar event.

    Args:
        title: The event title.
        start: Event start in 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' format.
        end: Event end in 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' format.
        calendar: Name of the target calendar (e.g. 'Work', 'Personal'). Leave empty for the system default calendar.
        location: Event location. Leave empty if none.
        notes: Event notes or description. Leave empty if none.
        is_all_day: Set to true for an all-day event.
        timezone: IANA timezone name (e.g. 'Europe/Berlin', 'America/New_York') if the times should be interpreted in a specific timezone. Leave empty to use the local timezone.

    Returns:
        The created event details including its event ID.
    """
    set_tool_message(f'Adding "{title}" to calendar')
    store = _get_store()
    tz = timezone or None
    dt_start = _parse_datetime(start, tz)
    dt_end = _parse_datetime(end, tz)
    event = store.add_event(
        title=title,
        start=dt_start,
        end=dt_end,
        calendar=calendar or None,
        location=location or None,
        notes=notes or None,
        is_all_day=is_all_day,
    )
    return "Event created:\n\n" + _format_event(event)


@macllm_tool
def cal_update_event(
    event_id: str,
    title: str = "",
    start: str = "",
    end: str = "",
    location: str = "\x00",
    notes: str = "\x00",
    timezone: str = "",
) -> str:
    """
    Update an existing calendar event. Only provide the fields you want to change.

    Args:
        event_id: The event ID (short or full, from a previous search or add result).
        title: New event title. Leave empty to keep the current title.
        start: New start time in 'YYYY-MM-DD HH:MM' format. Leave empty to keep current.
        end: New end time in 'YYYY-MM-DD HH:MM' format. Leave empty to keep current.
        location: New location. Leave empty to keep current. Set to 'CLEAR' to remove the location.
        notes: New notes. Leave empty to keep current. Set to 'CLEAR' to remove notes.
        timezone: IANA timezone name for interpreting start/end times. Leave empty for local timezone.

    Returns:
        The updated event details.
    """
    set_tool_message(f"Updating event {event_id}")
    store = _get_store()
    full_id = _resolve_event(event_id).event_id
    tz = timezone or None

    kwargs: dict = {}
    if title:
        kwargs["title"] = title
    if start:
        kwargs["start"] = _parse_datetime(start, tz)
    if end:
        kwargs["end"] = _parse_datetime(end, tz)

    # Sentinel: \x00 means "not provided" (keep current), empty string means "clear"
    if location != "\x00":
        kwargs["location"] = None if location == "CLEAR" else (location or ...)
    if notes != "\x00":
        kwargs["notes"] = None if notes == "CLEAR" else (notes or ...)

    event = store.update_event(full_id, **kwargs)
    return "Event updated:\n\n" + _format_event(event)


@macllm_tool
def cal_find_free_time(
    start: str,
    end: str,
    duration_minutes: int,
    calendars: str = "",
    timezone: str = "",
) -> str:
    """
    Find free time slots in a date range where no events are scheduled.

    Args:
        start: Window start in 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' format.
        end: Window end in 'YYYY-MM-DD HH:MM' or 'YYYY-MM-DD' format.
        duration_minutes: Minimum free slot length in minutes (e.g. 30, 60).
        calendars: Optional comma-separated calendar names to consider. Leave empty for all.
        timezone: IANA timezone name for interpreting the time window. Leave empty for local timezone.

    Returns:
        A list of free time slots, or a message if none found.
    """
    set_tool_message(f"Finding free time ({duration_minutes} min)")
    store = _get_store()
    tz = timezone or None
    dt_start = _parse_datetime(start, tz)
    dt_end = _parse_datetime(end, tz)
    duration = timedelta(minutes=duration_minutes)
    cal_list = _parse_csv(calendars)
    slots = store.find_free_time(
        dt_start, dt_end, duration, calendars=cal_list
    )
    if not slots:
        return "No free time slots found matching the criteria."
    return "\n".join(_format_time_slot(s) for s in slots)
