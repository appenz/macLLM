from datetime import datetime
from smolagents import tool


@tool
def get_current_time() -> str:
    """
    Returns the current local time and date.

    Returns:
        A string with the current date and time in format "YYYY-MM-DD HH:MM:SS"
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
