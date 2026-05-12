from macllm.agents.base import MacLLMAgent


class CalendarAgent(MacLLMAgent):
    """Subagent for calendar operations.

    Handles finding, creating, and editing calendar events and finding
    free time slots on the user's macOS calendars.
    Instructions are loaded from ``[agents.calendar]`` in config.toml.
    """

    macllm_name = "calendar"
    macllm_description = (
        "Finds, creates, and edits calendar events and finds free time "
        "slots on the user's macOS calendars."
    )
    macllm_tools = [
        "web_search",
        "cal_list_calendars",
        "cal_get_events",
        "cal_find_events",
        "cal_get_event",
        "cal_add_event",
        "cal_update_event",
        "cal_find_free_time",
    ]

    def __init__(self, **kwargs):
        super().__init__(planning_interval=None, **kwargs)
