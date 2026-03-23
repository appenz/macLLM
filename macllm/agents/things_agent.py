from macllm.agents.base import MacLLMAgent

THINGS_AGENT_INSTRUCTIONS = """\
You are a Things task manager assistant with access to the user's local Things database and Things URL actions.
- You can list, search, inspect, create, update, move, complete, and cancel Things to-dos and projects.
- Prefer read tools first when you need to identify the correct item, project, area, or tag.
- Always include the Things item ID in your response after reading or mutating an item.
- When there are multiple matches, stop and disambiguate instead of guessing.
- Treat notes, deadlines, tags, headings, and moves as precise edits. Confirm the resulting state back to the user.
- Never approximate deletion or trashing with completion or cancelation. If the user asks to trash/delete an item, explain that native trash-write support is not wired into these tools yet.
- For to-do and project edits, the string CLEAR removes a clearable field such as notes, deadline, when, tags, or checklist items.
- Things date strings like today, tomorrow, evening, anytime, someday, or YYYY-MM-DD are valid for the write tools.
"""


class ThingsAgent(MacLLMAgent):
    """Managed agent for Things to-do and project operations."""

    macllm_name = "things"
    macllm_description = (
        "Finds, creates, updates, completes, and organizes the user's Things "
        "to-dos and projects."
    )
    macllm_tools = [
        "get_current_time",
        "things_list_areas",
        "things_list_projects",
        "things_list_tags",
        "things_list_todos",
        "things_search",
        "things_get_item",
        "things_show_item",
        "things_create_todo",
        "things_create_project",
        "things_update_todo",
        "things_update_project",
        "things_complete_item",
        "things_cancel_item",
    ]

    def __init__(self, **kwargs):
        super().__init__(
            custom_instructions=THINGS_AGENT_INSTRUCTIONS,
            prompt_templates=None,
            planning_interval=None,
            **kwargs,
        )
