import pytest
import time

from macllm.macllm import create_macllm
from unittest.mock import Mock, patch


def _mock_agent_for_thread():
    """Agent thread calls len(agent.memory.steps) before run(); bare Mock breaks len()."""
    mock_agent = Mock()
    mock_agent.run = Mock(return_value="MOCK_RESPONSE")
    mock_agent.model = Mock()
    mock_agent.model.model_id = "openai/mercury"
    mock_agent.memory = Mock()
    mock_agent.memory.steps = []
    return mock_agent


def _wait_for_idle(conv, timeout=2.0):
    """Spin until the conversation's agent thread has exited."""
    deadline = time.monotonic() + timeout
    while conv.is_agent_running() and time.monotonic() < deadline:
        time.sleep(0.05)


class TestStickySpeedPreference:
    def test_speed_persists_within_conversation_and_resets_on_new(self):
        mac = create_macllm(debug=False, start_ui=False)

        assert mac.chat_history.speed_level == "normal"

        # Mock agent.run at the module level so it persists through agent recreation
        with patch('macllm.core.agent_service.create_agent') as mock_create_agent:
            mock_agent = _mock_agent_for_thread()
            mock_create_agent.return_value = mock_agent

            mac.chat_history.submit("Hello /fast")
            assert mac.chat_history.speed_level == "fast"
            _wait_for_idle(mac.chat_history)
            assert mock_agent.run.called

        # Verify speed persisted
        assert mac.chat_history.speed_level == "fast"

        # Test that speed persists without tag
        with patch('macllm.core.agent_service.create_agent') as mock_create_agent:
            mock_agent = _mock_agent_for_thread()
            mock_create_agent.return_value = mock_agent

            mac.chat_history.submit("Second message with no tag")
            assert mac.chat_history.speed_level == "fast"
            _wait_for_idle(mac.chat_history)

        # Test slow speed
        with patch('macllm.core.agent_service.create_agent') as mock_create_agent:
            mock_agent = _mock_agent_for_thread()
            mock_agent.model.model_id = "gpt-5"
            mock_create_agent.return_value = mock_agent

            mac.chat_history.submit("Please reason carefully /think")
            assert mac.chat_history.speed_level == "slow"
            _wait_for_idle(mac.chat_history)

        # Test new conversation resets speed
        new_conv = mac.conversation_history.add_conversation()
        new_conv.ui_update_callback = mac._update_ui_from_callback
        mac.chat_history = new_conv
        assert mac.chat_history.speed_level == "normal"

        with patch('macllm.core.agent_service.create_agent') as mock_create_agent:
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="MOCK_RESPONSE")
            mock_create_agent.return_value = mock_agent
            
            mac.chat_history.submit("Fresh start")
            assert mac.chat_history.speed_level == "normal"
            _wait_for_idle(mac.chat_history)
