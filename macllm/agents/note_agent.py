from macllm.agents.base import MacLLMAgent


class NoteAgent(MacLLMAgent):
    """Subagent for note operations.

    Handles searching, reading, creating, modifying, moving, and deleting
    notes within the user's personal notes folders.
    Instructions are loaded from ``[agents.notes]`` in config.toml.
    """

    macllm_name = "notes"
    macllm_description = (
        "Searches, reads, creates, modifies, moves, and deletes "
        "the user's local notes; creates and deletes folders within indexed roots. "
        "Can map note paths to absolute system paths."
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
        super().__init__(
            prompt_templates=None,
            planning_interval=None,
            **kwargs,
        )
