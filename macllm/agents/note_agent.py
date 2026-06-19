from macllm.agents.base import MacLLMAgent


class NoteAgent(MacLLMAgent):
    """Subagent for note operations.

    Handles searching, reading, creating, modifying, moving, and deleting
    notes within the user's personal notes folders.
    Instructions are loaded from ``[agents.notes]`` in config.toml.
    """

    macllm_name = "notes"
    macllm_description = (
        "Notes specialist for mechanical note storage operations only: search, read, create, append, modify, move, delete, list folders. Do not delegate summarization, rewriting, formatting, categorization, filing judgment, or user-facing response decisions. If content must be written, pass the exact final text."
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
