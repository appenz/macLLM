from macllm.agents.base import MacLLMAgent

NOTE_AGENT_INSTRUCTIONS = """\
You are a notes management assistant.
- You can search, read, create, append to, modify, move, and delete notes.
- All note operations are scoped to the user's indexed folders.
- If you can't find a note right away, try up to 5 different search queries and then ask the user for additional information.
- Never create a note without the user's explicit instructions.
- If asked to append to a note that doesn't exist, report the error -- do not create it.
- note_modify and note_delete automatically create backups. Mention the backup in your response.
- note_move will refuse to overwrite an existing note. Suggest a different name if there is a conflict.
- Provide the note path in your response so the user knows which note was affected.
"""


class NoteAgent(MacLLMAgent):
    """Subagent for note operations.

    Handles searching, reading, creating, modifying, moving, and deleting
    notes within the user's personal notes folders.
    """

    macllm_name = "notes"
    macllm_description = (
        "Searches, reads, creates, modifies, moves, and deletes "
        "the user's local notes."
    )
    macllm_tools = [
        "search_notes",
        "read_note",
        "note_create",
        "note_append",
        "note_modify",
        "note_move",
        "note_delete",
        "list_folder",
        "view_folder_structure",
    ]

    def __init__(self, **kwargs):
        super().__init__(
            custom_instructions=NOTE_AGENT_INSTRUCTIONS,
            prompt_templates=None,
            planning_interval=None,
            **kwargs,
        )
