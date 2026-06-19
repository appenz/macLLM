import threading
import time

from macllm.core.chat_history import Conversation
from macllm.core.context import set_current_conversation, _thread_context
from macllm.tools.user_input import ask_user


def _clear_current_conversation():
    from macllm.macllm import MacLLM
    _thread_context.conversation = None
    MacLLM._instance = None


def test_ask_user_returns_unavailable_without_conversation():
    _clear_current_conversation()

    assert ask_user("Question?") == "Input request unavailable."


def test_ask_user_waits_for_conversation_response():
    conv = Conversation()
    set_current_conversation(conv)
    result_holder = []

    def run_tool():
        set_current_conversation(conv)
        try:
            result_holder.append(ask_user("Which folder?"))
        finally:
            _clear_current_conversation()

    thread = threading.Thread(target=run_tool)
    thread.start()

    deadline = time.time() + 2
    while conv.pending_user_input is None and time.time() < deadline:
        time.sleep(0.01)

    assert conv.pending_user_input is not None
    assert conv.messages == [
        {"role": "assistant", "content": "Which folder?"},
    ]

    conv.submit("a16z/Pitches 2026")
    thread.join(timeout=2)

    assert result_holder == ["a16z/Pitches 2026"]
    assert conv.pending_user_input is None


def test_ask_user_does_not_block_task_mode_agent():
    conv = Conversation()
    conv.agent = type("Agent", (), {"_task_mode": True})()
    set_current_conversation(conv)
    try:
        assert ask_user("Question?") == "Input request unavailable."
    finally:
        _clear_current_conversation()
