from macllm.agents.base import MacLLMAgent

GRANOLA_AGENT_INSTRUCTIONS = """\
You are a Granola meeting notes assistant with read-only access to the user's Granola notes.
- You can list meetings, search meetings, read full meeting details and notes, get transcripts, and browse the people directory.
- You CANNOT create, edit, or delete meetings. If the user asks, explain that Granola access is read-only.
- Start with granola_list_meetings or granola_find_meetings to locate relevant meetings.
- Use granola_get_meeting to retrieve full notes, overview, and summary for a specific meeting.
- Use granola_get_transcript to get the spoken transcript of a meeting.
- Always include the meeting ID in your responses so the user can refer to it in follow-up queries.
- When searching, try different queries or field restrictions if the first search doesn't find what the user is looking for.
- If the user asks about a person, use granola_list_people or granola_find_meetings with attendee fields.
"""


class GranolaAgent(MacLLMAgent):
    """Subagent for Granola meeting notes (read-only).

    Searches and reads the user's Granola meeting notes, transcripts,
    and people directory from the local Granola cache.
    """

    macllm_name = "granola"
    macllm_description = (
        "Searches and reads the user's Granola meeting notes, "
        "transcripts, and people directory. "
        "To get a list of all meetings, pass 'LIST_ALL' as the task."
    )
    macllm_tools = [
        "get_current_time",
        "granola_list_meetings",
        "granola_find_meetings",
        "granola_get_meeting",
        "granola_get_transcript",
        "granola_list_people",
    ]

    def __init__(self, **kwargs):
        super().__init__(
            custom_instructions=GRANOLA_AGENT_INSTRUCTIONS,
            prompt_templates=None,
            planning_interval=None,
            **kwargs,
        )

    def __call__(self, task, **kwargs):
        """Fast-path certain operations to avoid unnecessary LLM round-trips."""
        result = self._try_fast_path(task)
        if result is not None:
            return result
        return super().__call__(task, **kwargs)

    def _try_fast_path(self, task: str) -> str | None:
        if "LIST_ALL" in task:
            from macllm.tools.granola import _get_store, _format_meetings_table

            store = _get_store()
            meetings = store.list_meetings()
            if not meetings:
                return "No Granola meetings found."
            return _format_meetings_table(meetings[:50], total=len(meetings))
        return None
