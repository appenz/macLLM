import threading
import time
from unittest.mock import Mock

from macllm.core.chat_history import Conversation
from macllm.core.agent_status import PendingUserInput


def test_submit_resolves_pending_user_input_before_queueing():
    conv = Conversation()
    conv.agent_thread = Mock()
    conv.agent_thread.is_alive = Mock(return_value=True)
    conv.pending_user_input = PendingUserInput(question="Which folder?")

    conv.submit("Use a16z/Pitches 2026")

    assert conv.pending_input == ""
    assert conv.pending_user_input.response == "Use a16z/Pitches 2026"
    assert conv.pending_user_input.event.is_set()
    assert conv.messages == [
        {"role": "user", "content": "Use a16z/Pitches 2026"},
    ]


def test_request_user_input_records_question_and_answer():
    conv = Conversation()
    result_holder = []

    def wait_for_input():
        result_holder.append(conv.request_user_input("Which note should I update?"))

    thread = threading.Thread(target=wait_for_input)
    thread.start()

    deadline = time.time() + 2
    while conv.pending_user_input is None and time.time() < deadline:
        time.sleep(0.01)

    assert conv.pending_user_input is not None
    assert conv.messages == [
        {"role": "assistant", "content": "Which note should I update?"},
    ]

    conv.submit("The weekly note")
    thread.join(timeout=2)

    assert result_holder == ["The weekly note"]
    assert conv.pending_user_input is None
    assert conv.messages == [
        {"role": "assistant", "content": "Which note should I update?"},
        {"role": "user", "content": "The weekly note"},
    ]


def test_abort_cancels_pending_user_input():
    conv = Conversation()
    conv.agent_thread = Mock()
    conv.agent_thread.is_alive = Mock(return_value=True)
    conv.agent = Mock()
    conv.agent.managed_agents = {}
    conv.pending_user_input = PendingUserInput(question="Continue?")

    conv.abort()

    assert conv.pending_user_input.cancelled is True
    assert conv.pending_user_input.event.is_set()
