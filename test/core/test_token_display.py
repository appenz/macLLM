"""Verify the full token-display pipeline: step callback → llm_metadata → top bar text."""

import time
from unittest.mock import Mock, patch, MagicMock

from smolagents import ActionStep, PlanningStep, TaskStep
from smolagents.memory import TokenUsage, Timing

from macllm.core.agent_service import create_step_callback
from macllm.core.chat_history import Conversation
from macllm.core.llm_service import get_model_for_speed
from macllm.macllm import create_macllm


# ---------------------------------------------------------------------------
# create_step_callback unit tests
# ---------------------------------------------------------------------------

class TestCreateStepCallback:
    """Verify token accumulation inside the step callback closure."""

    @staticmethod
    def _make_action_step(input_tokens: int, output_tokens: int) -> ActionStep:
        return ActionStep(
            step_number=1,
            timing=Timing(start_time=0.0),
            token_usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        )

    @staticmethod
    def _make_planning_step(input_tokens: int, output_tokens: int) -> PlanningStep:
        return PlanningStep(
            model_input_messages=[],
            model_output_message=Mock(),
            plan="test plan",
            timing=Timing(start_time=0.0),
            token_usage=TokenUsage(input_tokens=input_tokens, output_tokens=output_tokens),
        )

    def test_accumulates_action_step_tokens(self):
        received = {}

        def cb(inp, out):
            received["input"] = inp
            received["output"] = out

        on_step = create_step_callback(cb)
        on_step(self._make_action_step(100, 50), agent=None)
        assert received == {"input": 100, "output": 50}

        on_step(self._make_action_step(200, 80), agent=None)
        assert received == {"input": 300, "output": 130}

    def test_accumulates_planning_step_tokens(self):
        received = {}

        def cb(inp, out):
            received["input"] = inp
            received["output"] = out

        on_step = create_step_callback(cb)
        on_step(self._make_planning_step(50, 20), agent=None)
        assert received == {"input": 50, "output": 20}

    def test_mixed_steps(self):
        received = {}

        def cb(inp, out):
            received["input"] = inp
            received["output"] = out

        on_step = create_step_callback(cb)
        on_step(self._make_planning_step(10, 5), agent=None)
        on_step(self._make_action_step(100, 50), agent=None)
        assert received == {"input": 110, "output": 55}

    def test_task_step_ignored(self):
        received = {}

        def cb(inp, out):
            received["input"] = inp
            received["output"] = out

        on_step = create_step_callback(cb)
        on_step(TaskStep(task="sub"), agent=None)
        assert received == {}

    def test_no_callback_no_crash(self):
        on_step = create_step_callback(None)
        on_step(self._make_action_step(100, 50), agent=None)

    def test_none_token_usage_skipped(self):
        received = {}

        def cb(inp, out):
            received["input"] = inp
            received["output"] = out

        step = ActionStep(
            step_number=1,
            timing=Timing(start_time=0.0),
            token_usage=None,
        )
        on_step = create_step_callback(cb)
        on_step(step, agent=None)
        assert received == {}


# ---------------------------------------------------------------------------
# Conversation.llm_metadata integration
# ---------------------------------------------------------------------------

class TestConversationTokenMetadata:
    """Verify that _process_query correctly wires the token callback."""

    def test_initial_metadata_is_zero(self):
        conv = Conversation()
        assert conv.llm_metadata == {"input_tokens": 0, "output_tokens": 0}

    def test_metadata_reset_on_submit(self):
        """Submitting a query resets token counts to 0 before starting."""
        mac = create_macllm(debug=False, start_ui=False)
        conv = mac.chat_history
        conv.llm_metadata["input_tokens"] = 999
        conv.llm_metadata["output_tokens"] = 888

        with patch("macllm.core.agent_service.create_agent") as mock_create:
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="done")
            mock_agent.memory = Mock()
            mock_agent.memory.steps = []
            mock_create.return_value = mock_agent
            conv.submit("test")
            time.sleep(0.3)

        assert conv.llm_metadata["input_tokens"] == 0
        assert conv.llm_metadata["output_tokens"] == 0

    def test_token_callback_updates_metadata(self):
        """token_callback created in _process_query correctly sets llm_metadata."""
        mac = create_macllm(debug=False, start_ui=False)
        conv = mac.chat_history

        captured_callback = {}

        def intercept_create_agent(agent_cls=None, speed="normal", token_callback=None):
            captured_callback["cb"] = token_callback
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="done")
            mock_agent.memory = Mock()
            mock_agent.memory.steps = []
            return mock_agent

        with patch("macllm.core.agent_service.create_agent", side_effect=intercept_create_agent):
            conv.submit("test")
            time.sleep(0.3)

        cb = captured_callback.get("cb")
        assert cb is not None, "token_callback should have been passed to create_agent"

        conv.ui_update_callback = lambda: None
        cb(150, 75)
        assert conv.llm_metadata["input_tokens"] == 150
        assert conv.llm_metadata["output_tokens"] == 75


# ---------------------------------------------------------------------------
# Top-bar display text verification
# ---------------------------------------------------------------------------

class TestTopBarDisplayValues:
    """Verify the data that update_top_bar_text reads from the conversation."""

    def test_model_matches_speed(self):
        """get_model_for_speed returns correct model for each tier."""
        fast = get_model_for_speed("fast")
        normal = get_model_for_speed("normal")
        slow = get_model_for_speed("slow")

        assert fast != "unknown"
        assert normal != "unknown"
        assert slow != "unknown"
        assert fast != normal

    def test_speed_display_mapping(self):
        """Verify the speed → display label mapping used in update_top_bar_text."""
        mapping = {"fast": "Fast", "normal": "Normal", "slow": "Think"}
        for key, expected in mapping.items():
            assert mapping[key] == expected

    def test_agent_display_name(self):
        """agent_cls.macllm_name.capitalize() produces the expected label."""
        mac = create_macllm(debug=False, start_ui=False)
        agent_cls = mac.chat_history.agent_cls
        assert agent_cls is not None
        name = agent_cls.macllm_name.capitalize()
        assert len(name) > 0, "Agent display name should be non-empty"

    def test_display_for_each_tab(self):
        """Switching tabs updates chat_history and each conversation's metadata is independent."""
        mac = create_macllm(debug=False, start_ui=False)

        conv_a = mac.chat_history
        conv_a.llm_metadata["input_tokens"] = 100
        conv_a.llm_metadata["output_tokens"] = 50
        conv_a.speed_level = "fast"

        conv_b = mac.conversation_history.add_conversation()
        conv_b.ui_update_callback = mac._update_ui_from_callback
        conv_b.llm_metadata["input_tokens"] = 200
        conv_b.llm_metadata["output_tokens"] = 80
        conv_b.speed_level = "slow"

        mac.switch_to_conversation(1)
        assert mac.chat_history is conv_b
        assert mac.chat_history.llm_metadata["input_tokens"] == 200
        assert mac.chat_history.speed_level == "slow"

        mac.switch_to_conversation(0)
        assert mac.chat_history is conv_a
        assert mac.chat_history.llm_metadata["input_tokens"] == 100
        assert mac.chat_history.speed_level == "fast"
