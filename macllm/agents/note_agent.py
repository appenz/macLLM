from macllm.agents.base import MacLLMAgent

NOTE_AGENT_INSTRUCTIONS = """\
You are a notes management assistant.
- You can search, read, create, append to, modify, move, and delete notes, and create or delete folders.
- All note paths use mount-point names, e.g. "Notes/todo.md" or "Work/projects/plan.md". Use view_folder_structure to discover available mounts and their contents.
- If you can't find a note right away, try up to 5 different search queries and then ask the user for additional information.
- Never create a note without the user's explicit instructions.
- If asked to append to a note that doesn't exist, report the error -- do not create it.
- note_modify, note_delete, and folder_delete automatically create backups. Mention the backup in your response.
- note_move will refuse to overwrite an existing note. Suggest a different name if there is a conflict.
- folder_create requires the parent folder to exist (create nested folders one level at a time).
- folder_delete cannot remove a mount-point root; only subfolders.
- Provide the note path in your response so the user knows which note was affected.
- You can resolve a note path to an absolute filesystem path with note_resolve_path when needed.
"""


class NoteAgent(MacLLMAgent):
    """Subagent for note operations.

    Handles searching, reading, creating, modifying, moving, and deleting
    notes within the user's personal notes folders.
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
            custom_instructions=NOTE_AGENT_INSTRUCTIONS,
            prompt_templates=None,
            planning_interval=None,
            **kwargs,
        )
