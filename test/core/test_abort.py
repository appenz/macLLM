"""Verify the abort / interrupt path records a static message and never calls provide_final_answer."""

import threading
import time
from unittest.mock import Mock, patch, PropertyMock

from macllm.core.chat_history import Conversation
from macllm.macllm import create_macllm


class TestAbortMessage:
    """_handle_abort_summary must add 'Interrupted.' without an LLM call."""

    def test_abort_adds_static_message(self):
        conv = Conversation()
        app = Mock()
        app.ephemeral = True

        conv.agent = Mock()
        conv._handle_abort_summary("ignored task", app)

        assistant_msgs = [m for m in conv.messages if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["content"] == "Interrupted."

    def test_abort_does_not_call_provide_final_answer(self):
        conv = Conversation()
        app = Mock()
        app.ephemeral = True

        conv.agent = Mock()
        conv._handle_abort_summary("ignored task", app)

        conv.agent.provide_final_answer.assert_not_called()

    def test_abort_saves_when_not_ephemeral(self):
        conv = Conversation()
        app = Mock()
        app.ephemeral = False

        conv.agent = Mock()
        with patch("macllm.core.memory.save_all_conversations") as mock_save:
            conv._handle_abort_summary("ignored task", app)
            mock_save.assert_called_once_with(app.conversation_history)

    def test_abort_skips_save_when_ephemeral(self):
        conv = Conversation()
        app = Mock()
        app.ephemeral = True

        conv.agent = Mock()
        with patch("macllm.core.memory.save_all_conversations") as mock_save:
            conv._handle_abort_summary("ignored task", app)
            mock_save.assert_not_called()

    def test_full_abort_flow_via_agent_thread(self):
        """Submit triggers agent.run; abort_event causes the exception path
        to route to _handle_abort_summary with a static message."""
        mac = create_macllm(debug=False, start_ui=False)
        conv = mac.chat_history

        started = threading.Event()

        def blocking_run(*args, **kwargs):
            started.set()
            # Wait until abort_event is set, then raise like smolagents does
            conv.abort_event.wait(timeout=5)
            raise RuntimeError("Agent interrupted.")

        with patch("macllm.core.agent_service.create_agent") as mock_create:
            mock_agent = Mock()
            mock_agent.run = Mock(side_effect=blocking_run)
            mock_agent.memory = Mock()
            mock_agent.memory.steps = []
            mock_agent.interrupt_switch = False
            type(mock_agent).managed_agents = PropertyMock(return_value={})
            mock_create.return_value = mock_agent

            conv.submit("test")
            started.wait(timeout=2)
            conv.abort()
            time.sleep(0.5)

        assistant_msgs = [m for m in conv.messages if m["role"] == "assistant"]
        assert any(m["content"] == "Interrupted." for m in assistant_msgs)
        mock_agent.provide_final_answer.assert_not_called()
