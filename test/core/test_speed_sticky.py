import pytest

from macllm.macllm import create_macllm
from unittest.mock import Mock, patch


class TestStickySpeedPreference:
    def test_speed_persists_within_conversation_and_resets_on_new(self):
        with patch('macllm.core.llm_service.completion') as mock_completion:
            mock_response = Mock()
            mock_response.choices = [Mock(message=Mock(content="MOCK_RESPONSE"))]
            mock_response.usage = Mock(total_tokens=0)
            mock_completion.return_value = mock_response
            
            mac = create_macllm(debug=False, start_ui=False)

            assert mac.chat_history.speed_level == "normal"

            mac.handle_instructions("Hello /fast")
            assert mac.chat_history.speed_level == "fast"
            
            call_args = mock_completion.call_args_list[-1]
            assert call_args.kwargs.get('model') == 'openai/mercury'

            mac.handle_instructions("Second message with no tag")
            assert mac.chat_history.speed_level == "fast"

            mac.handle_instructions("Please reason carefully /think")
            assert mac.chat_history.speed_level == "slow"

            new_conv = mac.conversation_history.add_conversation()
            mac.chat_history = new_conv
            assert mac.chat_history.speed_level == "normal"

            mac.handle_instructions("Fresh start")
            assert mac.chat_history.speed_level == "normal"
