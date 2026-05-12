# Calendar Integration

## Overview

The calendar subsystem combines a specialist agent with a small set of calendar tools.

- `CalendarAgent` provides the scheduling-focused instructions and tool set
- `macllm/tools/calendar.py` provides the actual calendar operations

This keeps scheduling behavior separate from the main assistant while still allowing delegation from top-level agents.

## Design

Calendar tools are a thin wrapper over macOS calendar access through `maccal` and EventKit.

The design is intentionally string-oriented:

- tool inputs use simple string parameters
- tool outputs are human-readable summaries, not structured JSON
- event IDs are the stable handle for follow-up edits

## Tool Model

The calendar tool family covers:

- calendar listing
- event lookup (compact summaries via `cal_get_events` / `cal_find_events`)
- single event detail retrieval (`cal_get_event`)
- text search over events
- event creation
- event updates
- free-time search

Dates use `YYYY-MM-DD HH:MM` or `YYYY-MM-DD`. Timezones are optional and use IANA names when specified.

### Two-Tier Event Display

Search and list tools (`cal_get_events`, `cal_find_events`) return compact summaries that omit
notes, URLs, availability, and trim attendees to the first 5. This keeps token usage low when
scanning many events.

`cal_get_event` returns full details for a single event by ID — including notes, all attendees
with RSVP, URLs, and recurrence info.

### Short Event IDs

Events are identified by short IDs in the format `YYYY-MM-DD-<4 hex>` (e.g. `2026-05-11-a3f2`).
The date is the event start in UTC; the hex suffix is the first 4 characters of the SHA-256 hash
of the full EventKit ID. Resolution is stateless: fetch all events for that UTC date and match
by hash. All tools that accept an event ID (`cal_get_event`, `cal_update_event`) resolve short
IDs automatically and also accept full EventKit IDs as a fallback.

## Limits

The current subsystem supports common scheduling flows, but not the full calendar feature set.

- attendees cannot be managed through these tools
- recurrence support is limited
- writes target the user's default calendar unless another calendar is specified

Calendar tool progress is reported through the same status system as other tools.
