"""Calendar tools wrapping the maccal library for macOS EventKit access."""

import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from smolagents import tool

_tool_call_counter = {
    "cal_list_calendars": 0,
    "cal_get_events": 0,
    "cal_find_events": 0,
    "cal_add_event": 0,
    "cal_update_event": 0,
    "cal_find_free_time": 0,
}

_store_singleton = None


def _get_store():
    """Lazy-initialize a singleton CalendarStore."""
    global _store_singleton
    if _store_singleton is None:
        from maccal import CalendarStore

        _store_singleton = CalendarStore()
    return _store_singleton


def _status_manager():
    from macllm.macllm import MacLLM

    return MacLLM.get_status_manager()


def _make_tool_id(name: str) -> str:
    _tool_call_counter[name] += 1
    return f"{name}_{_tool_call_counter[name]}_{int(time.time() * 1000)}"


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
        names = [a.name or a.email or "unknown" for a in ev.attendees]
        lines.append(f"  Attendees: {', '.join(names)}")
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
# Tools
# ---------------------------------------------------------------------------


@tool
def cal_list_calendars() -> str:
    """
    List all available macOS calendars.

    Returns:
        A formatted list of calendars showing name, type, and source.
    """
    tool_id = _make_tool_id("cal_list_calendars")
    status = _status_manager()
    status.start_tool_call(tool_id, "cal_list_calendars", {})

    try:
        store = _get_store()
        cals = store.list_calendars()
        if not cals:
            status.complete_tool_call(tool_id, "0 calendars")
            return "No calendars found."
        lines = []
        for c in cals:
            parts = [c.title, f"type={c.type.name.lower()}"]
            if c.source:
                parts.append(f"source={c.source}")
            lines.append("- " + ", ".join(parts))
        result = "\n".join(lines)
        status.complete_tool_call(tool_id, f"{len(cals)} calendars")
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
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
    tool_id = _make_tool_id("cal_get_events")
    status = _status_manager()
    status.start_tool_call(tool_id, "cal_get_events", {"start": start, "end": end})

    try:
        store = _get_store()
        dt_start = _parse_datetime(start)
        dt_end = _parse_datetime(end)
        cal_list = _parse_csv(calendars)
        events = store.get_events(dt_start, dt_end, calendars=cal_list)
        if not events:
            status.complete_tool_call(tool_id, "0 events")
            return "No events found in this range."
        result = "\n\n".join(_format_event(ev) for ev in events)
        status.complete_tool_call(tool_id, f"{len(events)} events")
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
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
    tool_id = _make_tool_id("cal_find_events")
    status = _status_manager()
    status.start_tool_call(tool_id, "cal_find_events", {"query": query})

    try:
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
            status.complete_tool_call(tool_id, "0 matches")
            return f"No events matching '{query}' found in this range."
        result = "\n\n".join(_format_event(ev) for ev in events)
        status.complete_tool_call(tool_id, f"{len(events)} matches")
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
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
    tool_id = _make_tool_id("cal_add_event")
    status = _status_manager()
    status.start_tool_call(tool_id, "cal_add_event", {"title": title})

    try:
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
        result = "Event created:\n\n" + _format_event(event)
        status.complete_tool_call(tool_id, title[:30])
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
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
        event_id: The event ID (from a previous search or add result).
        title: New event title. Leave empty to keep the current title.
        start: New start time in 'YYYY-MM-DD HH:MM' format. Leave empty to keep current.
        end: New end time in 'YYYY-MM-DD HH:MM' format. Leave empty to keep current.
        location: New location. Leave empty to keep current. Set to 'CLEAR' to remove the location.
        notes: New notes. Leave empty to keep current. Set to 'CLEAR' to remove notes.
        timezone: IANA timezone name for interpreting start/end times. Leave empty for local timezone.

    Returns:
        The updated event details.
    """
    tool_id = _make_tool_id("cal_update_event")
    status = _status_manager()
    status.start_tool_call(tool_id, "cal_update_event", {"event_id": event_id})

    try:
        store = _get_store()
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

        event = store.update_event(event_id, **kwargs)
        result = "Event updated:\n\n" + _format_event(event)
        status.complete_tool_call(tool_id, event.title[:30])
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise


@tool
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
    tool_id = _make_tool_id("cal_find_free_time")
    status = _status_manager()
    status.start_tool_call(
        tool_id, "cal_find_free_time", {"duration": duration_minutes}
    )

    try:
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
            status.complete_tool_call(tool_id, "0 slots")
            return "No free time slots found matching the criteria."
        result = "\n".join(_format_time_slot(s) for s in slots)
        status.complete_tool_call(tool_id, f"{len(slots)} slots")
        return result
    except Exception as e:
        status.fail_tool_call(tool_id, str(e)[:50])
        raise
