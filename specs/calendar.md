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
- event lookup
- text search over events
- event creation
- event updates
- free-time search

Dates use `YYYY-MM-DD HH:MM` or `YYYY-MM-DD`. Timezones are optional and use IANA names when specified.

## Limits

The current subsystem supports common scheduling flows, but not the full calendar feature set.

- attendees cannot be managed through these tools
- recurrence support is limited
- writes target the user's default calendar unless another calendar is specified

Calendar tool progress is reported through the same status system as other tools.
