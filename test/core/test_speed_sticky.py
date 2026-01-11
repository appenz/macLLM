import pytest
import time

from macllm.macllm import create_macllm
from unittest.mock import Mock, patch


class TestStickySpeedPreference:
    def test_speed_persists_within_conversation_and_resets_on_new(self):
        mac = create_macllm(debug=False, start_ui=False)

        assert mac.chat_history.speed_level == "normal"

        # Mock agent.run at the module level so it persists through agent recreation
        with patch('macllm.core.agent_service.create_agent') as mock_create_agent:
            # Create a mock agent
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="MOCK_RESPONSE")
            mock_agent.model = Mock()
            mock_agent.model.model_id = 'openai/mercury'
            mock_create_agent.return_value = mock_agent
            
            mac.handle_instructions("Hello /fast")
            assert mac.chat_history.speed_level == "fast"
            time.sleep(0.3)
            assert mock_agent.run.called

        # Verify speed persisted
        assert mac.chat_history.speed_level == "fast"

        # Test that speed persists without tag
        with patch('macllm.core.agent_service.create_agent') as mock_create_agent:
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="MOCK_RESPONSE")
            mock_agent.model = Mock()
            mock_agent.model.model_id = 'openai/mercury'
            mock_create_agent.return_value = mock_agent
            
            mac.handle_instructions("Second message with no tag")
            assert mac.chat_history.speed_level == "fast"
            time.sleep(0.3)

        # Test slow speed
        with patch('macllm.core.agent_service.create_agent') as mock_create_agent:
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="MOCK_RESPONSE")
            mock_agent.model = Mock()
            mock_agent.model.model_id = 'gpt-5'
            mock_create_agent.return_value = mock_agent
            
            mac.handle_instructions("Please reason carefully /think")
            assert mac.chat_history.speed_level == "slow"
            time.sleep(0.3)

        # Test new conversation resets speed
        new_conv = mac.conversation_history.add_conversation()
        new_conv.ui_update_callback = mac._update_ui_from_callback
        mac.chat_history = new_conv
        assert mac.chat_history.speed_level == "normal"

        with patch('macllm.core.agent_service.create_agent') as mock_create_agent:
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="MOCK_RESPONSE")
            mock_create_agent.return_value = mock_agent
            
            mac.handle_instructions("Fresh start")
            assert mac.chat_history.speed_level == "normal"
            time.sleep(0.3)
