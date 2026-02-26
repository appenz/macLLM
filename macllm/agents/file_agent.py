from macllm.agents.base import MacLLMAgent

FILE_AGENT_INSTRUCTIONS = """\
You are a file and notes management assistant.
- You can search, read, create, append to, modify, move, and delete files.
- All file operations are scoped to the user's indexed directories.
- If you can't find a file right away, try different search queries before giving up.
- Never create a file without the user's explicit instructions.
- If asked to append to a file that doesn't exist, report the error -- do not create it.
- file_modify and file_delete automatically create backups. Mention the backup in your response.
- file_move will refuse to overwrite an existing file. Suggest a different name if there is a conflict.
- When the user says "notes" they mean local indexed files.
- Provide the file path in your response so the user knows which file was affected.
"""


class FileAgent(MacLLMAgent):
    """Subagent for file and notes operations.

    Handles searching, reading, creating, modifying, moving, and deleting
    files within the user's indexed directories.
    """

    macllm_name = "files"
    macllm_description = (
        "Searches, reads, creates, modifies, moves, and deletes "
        "the user's local files and notes."
    )
    macllm_tools = [
        "search_files",
        "read_file",
        "file_create",
        "file_append",
        "file_modify",
        "file_move",
        "file_delete",
        "list_directory",
        "view_directory_structure",
    ]

    def __init__(self, **kwargs):
        super().__init__(
            custom_instructions=FILE_AGENT_INSTRUCTIONS,
            prompt_templates=None,
            planning_interval=None,
            **kwargs,
        )
