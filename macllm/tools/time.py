from datetime import datetime

from macllm.tools._debug import macllm_tool, set_tool_message


@macllm_tool
def get_current_time() -> str:
    """
    Returns the current local time and date.

    Returns:
        A string with the current date and time in format "YYYY-MM-DD HH:MM:SS"
    """
    set_tool_message("Getting current time")
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
