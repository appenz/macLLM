"""Verify abort behaviour: immediate message, no LLM summary, no duplicate messages."""

import threading
import time
from unittest.mock import Mock, patch, PropertyMock

from macllm.core.chat_history import Conversation
from macllm.core.conversationlog import messages_from_log
from macllm.macllm import create_macllm


def _displayable(conv):
    return [m for m in messages_from_log(conv.conversation_log) if m["role"] in ("user", "assistant")]


class TestAbortMessage:
    """abort() adds an immediate 'Interrupted.' message; _handle_abort does not add another."""

    def test_abort_adds_immediate_message(self):
        """abort() adds 'Interrupted.' right away for visual feedback."""
        conv = Conversation()
        # Fake a running agent thread so abort() doesn't early-return
        conv.agent_thread = Mock()
        conv.agent_thread.is_alive = Mock(return_value=True)
        conv.agent = Mock()
        type(conv.agent).managed_agents = PropertyMock(return_value={})

        conv.abort()

        assistant_msgs = [m for m in _displayable(conv) if m["role"] == "assistant"]
        assert len(assistant_msgs) == 1
        assert assistant_msgs[0]["content"] == "Interrupted."

    def test_handle_abort_adds_no_extra_message(self):
        """_handle_abort must NOT add any assistant message (abort() already did)."""
        conv = Conversation()
        app = Mock()
        app.ephemeral = True

        conv.agent = Mock()
        conv._handle_abort(app)

        assistant_msgs = [m for m in _displayable(conv) if m["role"] == "assistant"]
        assert len(assistant_msgs) == 0

    def test_abort_saves_when_not_ephemeral(self):
        conv = Conversation()
        app = Mock()
        app.ephemeral = False

        conv.agent = Mock()
        with patch("macllm.core.memory.save_all_conversations") as mock_save:
            conv._handle_abort(app)
            mock_save.assert_called_once_with(app.conversation_history)

    def test_abort_skips_save_when_ephemeral(self):
        conv = Conversation()
        app = Mock()
        app.ephemeral = True

        conv.agent = Mock()
        with patch("macllm.core.memory.save_all_conversations") as mock_save:
            conv._handle_abort(app)
            mock_save.assert_not_called()

    def test_full_abort_flow_via_agent_thread(self):
        """Submit triggers agent.run; abort adds exactly one 'Interrupted.'
        message and the agent thread does not add another."""
        mac = create_macllm(debug=False, start_ui=False)
        conv = mac.chat_history

        started = threading.Event()

        def blocking_run(*args, **kwargs):
            started.set()
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

        interrupted_msgs = [m for m in _displayable(conv)
                            if m["role"] == "assistant" and m["content"] == "Interrupted."]
        assert len(interrupted_msgs) == 1, "Expected exactly one 'Interrupted.' message"
        mock_agent.provide_final_answer.assert_not_called()


class TestPendingInput:
    """Verify that pending_input accumulates and drains correctly."""

    def test_submit_while_running_accumulates(self):
        conv = Conversation()
        conv.agent_thread = Mock()
        conv.agent_thread.is_alive = Mock(return_value=True)

        conv.submit("first")
        assert conv.pending_input == "first"

        conv.submit("second")
        assert conv.pending_input == "first\nsecond"

        # No user messages should be added while accumulating
        user_msgs = [m for m in _displayable(conv) if m["role"] == "user"]
        assert len(user_msgs) == 0

    def test_submit_when_idle_does_not_accumulate(self):
        """When the agent is not running, submit processes immediately
        (which will fail here because no real agent, but pending_input
        should stay empty)."""
        conv = Conversation()
        conv.pending_input = ""
        try:
            conv.submit("hello")
        except Exception:
            pass
        assert conv.pending_input == ""

    def test_drain_pending_input(self):
        conv = Conversation()
        conv.pending_input = "combined query"

        drained = []
        conv._process_query = lambda q: drained.append(q)

        conv._drain_pending_input()

        assert drained == ["combined query"]
        assert conv.pending_input == ""

    def test_drain_empty_pending_input(self):
        conv = Conversation()
        conv.pending_input = ""

        drained = []
        conv._process_query = lambda q: drained.append(q)

        conv._drain_pending_input()

        assert drained == []


class TestAbortableModel:
    """Verify AbortableModel cancels generate() on abort_event."""

    def test_immediate_abort(self):
        from macllm.core.abortable_model import AbortableModel, AgentInterrupted

        abort_event = threading.Event()
        abort_event.set()

        inner = Mock()
        model = AbortableModel(inner, abort_event)

        try:
            model.generate()
            assert False, "Should have raised AgentInterrupted"
        except AgentInterrupted:
            pass

        inner.generate.assert_not_called()

    def test_abort_during_generate(self):
        from macllm.core.abortable_model import AbortableModel, AgentInterrupted

        abort_event = threading.Event()
        inner = Mock()

        call_started = threading.Event()

        def slow_generate(*args, **kwargs):
            call_started.set()
            time.sleep(5)
            return Mock()

        inner.generate = slow_generate
        model = AbortableModel(inner, abort_event)

        result_holder = [None]
        error_holder = [None]

        def run():
            try:
                result_holder[0] = model.generate()
            except AgentInterrupted as e:
                error_holder[0] = e

        t = threading.Thread(target=run)
        t.start()
        call_started.wait(timeout=2)
        abort_event.set()
        t.join(timeout=2)

        assert error_holder[0] is not None
        assert isinstance(error_holder[0], AgentInterrupted)

    def test_proxies_attributes(self):
        from macllm.core.abortable_model import AbortableModel

        inner = Mock()
        inner.model_id = "test-model"
        inner.api_key = "secret"

        model = AbortableModel(inner, threading.Event())

        assert model.model_id == "test-model"
        assert model.api_key == "secret"

    def test_successful_generate(self):
        from macllm.core.abortable_model import AbortableModel

        abort_event = threading.Event()
        inner = Mock()
        expected = Mock()
        inner.generate.return_value = expected

        model = AbortableModel(inner, abort_event)
        result = model.generate("prompt")

        assert result is expected
