from macllm.core.context import get_current_conversation
from macllm.tools._debug import macllm_tool, set_tool_message


def _can_wait_for_input(conversation) -> bool:
    if conversation is None:
        return False
    agent = getattr(conversation, "agent", None)
    if getattr(agent, "_task_mode", False):
        return False
    try:
        from macllm.macllm import MacLLM
        app = MacLLM._instance
        if app is not None and getattr(app, "ephemeral", False):
            return False
    except Exception:
        pass
    return True


@macllm_tool
def ask_user(question: str) -> str:
    """
    Ask the user one concise question and wait for their response.

    Use this when the next useful step depends on the user's intent,
    preference, missing data, or confirmation. The response is returned as
    this tool's observation so you can continue the current task.

    Args:
        question: The focused question to show in the normal chat conversation.
    """
    conversation = get_current_conversation()
    if not _can_wait_for_input(conversation):
        return "Input request unavailable."

    question = (question or "").strip()
    if not question:
        return "Input request cancelled: no question was provided."

    set_tool_message("Waiting for input")
    return conversation.request_user_input(question)
