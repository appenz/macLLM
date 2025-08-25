import pytest

from macllm.macllm import create_macllm
from macllm.models.fake_connector import FakeConnector


class TestStickySpeedPreference:
    def test_speed_persists_within_conversation_and_resets_on_new(self):
        mac = create_macllm(debug=False, start_ui=False)

        # Use fake provider so tests run offline
        mac.llm = FakeConnector()

        # Default is normal at conversation start
        assert mac.chat_history.speed_level == "normal"

        # First message sets @fast and should persist
        mac.handle_instructions("Hello @fast")
        assert mac.chat_history.speed_level == "fast"

        # Next message without tag should still use fast
        mac.handle_instructions("Second message with no tag")
        assert mac.chat_history.speed_level == "fast"

        # Switch to @think (treated as slow)
        mac.handle_instructions("Please reason carefully @think")
        assert mac.chat_history.speed_level == "slow"

        # Start a new conversation and verify defaults restored
        new_conv = mac.conversation_history.add_conversation()
        mac.chat_history = new_conv
        assert mac.chat_history.speed_level == "normal"

        # New conversation without tags keeps normal
        mac.handle_instructions("Fresh start")
        assert mac.chat_history.speed_level == "normal"


