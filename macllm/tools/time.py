import time
from datetime import datetime
from smolagents import tool

_tool_call_counter = [0]


@tool
def get_current_time() -> str:
    """
    Returns the current local time and date.

    Returns:
        A string with the current date and time in format "YYYY-MM-DD HH:MM:SS"
    """
    from macllm.macllm import MacLLM
    
    result = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Register completion (instant tool - no start needed)
    _tool_call_counter[0] += 1
    tool_id = f"get_current_time_{_tool_call_counter[0]}_{int(time.time() * 1000)}"
    MacLLM.get_status_manager().complete_tool_call(tool_id, result)
    
    return result
