from macllm.agents.base import MacLLMAgent
from macllm.tools.filesystem import FILESYSTEM_TOOLS


class CalendarAgent(MacLLMAgent):
    """Subagent for calendar operations.

    Handles finding, creating, and editing calendar events and finding
    free time slots on the user's macOS calendars.
    Instructions are loaded from ``[agents.calendar]`` in config.toml.
    """

    macllm_name = "calendar"
    read_only_no_hostfs = True
    macllm_description = (
        "Finds, creates, and edits calendar events and finds free time "
        "slots on the user's macOS calendars."
    )
    macllm_tools = [
        "web_search",
        "web_fetch",
        *FILESYSTEM_TOOLS,
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
