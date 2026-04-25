from macllm.agents.base import MacLLMAgent


class ThingsAgent(MacLLMAgent):
    """Managed agent for Things to-do and project operations.

    Instructions are loaded from ``[agents.things]`` in config.toml.
    """

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
        super().__init__(planning_interval=None, **kwargs)
