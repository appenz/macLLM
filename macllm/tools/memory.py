"""Memory tool: append timestamped notes to a daily memory file."""

import os
from datetime import datetime

from macllm.tags.file_tag import FileTag
from macllm.tools._debug import macllm_tool, set_tool_message

MEMORY_SUBFOLDER = "Agent-Memory"


def _memory_dir() -> str | None:
    """Resolve the memory directory from config or fall back to the first indexed folder."""
    from macllm.core.config import get_runtime_config

    cfg = get_runtime_config()
    configured = cfg.resolved_memory_dir()
    if configured:
        return configured

    if FileTag._indexed_directories:
        return os.path.join(FileTag._indexed_directories[0], MEMORY_SUBFOLDER)

    return None


@macllm_tool
def remember(text: str) -> str:
    """
    Save a piece of information to the agent's long-term memory.
    Use this to remember important facts, user preferences, decisions,
    or anything worth recalling in future conversations.
    Each day's memories are stored in a separate file.

    Args:
        text: The information to remember.

    Returns:
        Success message, or an error description.
    """
    set_tool_message("Saving to memory")
    mem_dir = _memory_dir()
    if mem_dir is None:
        return "Error: No indexed folders configured and no memory_dir set in config."

    try:
        os.makedirs(mem_dir, exist_ok=True)
    except OSError as e:
        return f"Error: Could not create memory folder {mem_dir}: {e}"

    now = datetime.now()
    filename = f"memory-{now:%y-%m-%d}.md"
    filepath = os.path.join(mem_dir, filename)

    try:
        exists = os.path.exists(filepath)
        with open(filepath, "a", encoding="utf-8") as f:
            if exists and os.path.getsize(filepath) > 0:
                f.write("\n")
            f.write(text)

        return f"Remembered in {filename}"
    except Exception as e:
        return f"Error writing memory: {e}"
