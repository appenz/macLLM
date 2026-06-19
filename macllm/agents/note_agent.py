from macllm.agents.base import MacLLMAgent


class NoteAgent(MacLLMAgent):
    """Subagent for note operations.

    Handles searching, reading, creating, modifying, moving, and deleting
    notes within the user's personal notes folders.
    Instructions are loaded from ``[agents.notes]`` in config.toml.
    """

    macllm_name = "notes"
    macllm_description = (
        "Agent that handles simple operations for the user's personal notes."
        "Use for finding, retrieving, creating, modifying, moving, appending to, and deleting notes."
        "Do not use for complex tasks such as summarizing, categorizing, or organizing notes."
    )
    macllm_tools = [
        "search_notes",
        "read_note",
        "note_resolve_path",
        "note_create",
        "note_append",
        "note_modify",
        "note_move",
        "note_delete",
        "list_folder",
        "find_folder",
        "view_folder_structure",
        "folder_create",
        "folder_delete",
    ]

    def __init__(self, **kwargs):
        super().__init__(planning_interval=None, **kwargs)
