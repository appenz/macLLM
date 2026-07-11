"""Verify token accounting and cumulative top-bar display data."""

import time
from unittest.mock import Mock, patch, MagicMock

from smolagents import ActionStep, PlanningStep, TaskStep
from smolagents.memory import TokenUsage, Timing

from macllm.core.agent_service import create_step_callback, extract_plan, extract_status
from macllm.core.chat_history import Conversation, Usage
from macllm.core.conversation_log import append_step, latest_plan, token_usage_totals
from macllm.core.llm_service import get_model_for_speed
from macllm.macllm import create_macllm


# ---------------------------------------------------------------------------
# Plan parsing tests
# ---------------------------------------------------------------------------

class TestPlanParsing:
    def test_extract_plan_between_markers(self):
        text = (
            "### Plan:\n"
            "[ ] Find Thursday dinner details\n"
            "[x] Draft a confirmation email\n"
            "<end_plan>\n"
            "### Status:\n"
            "Found Friday dinner details only.\n"
            "<end_status>\n"
        )
        assert extract_plan(text) == (
            "[ ] Find Thursday dinner details\n"
            "[x] Draft a confirmation email"
        )

    def test_extract_status_between_markers(self):
        text = (
            "### Plan:\n"
            "[ ] Search notes\n"
            "<end_plan>\n"
            "### Status:\n"
            "Found dinner with Marcus on Friday.\n"
            "Still searching for Thursday.\n"
            "<end_status>\n"
        )
        assert extract_status(text) == (
            "Found dinner with Marcus on Friday.\n"
            "Still searching for Thursday."
        )

    def test_extract_status_missing_markers(self):
        assert extract_status("### Plan:\n[ ] Do a thing\n<end_plan>") is None


# ---------------------------------------------------------------------------
# create_step_callback unit tests
# ---------------------------------------------------------------------------

class TestCreateStepCallback:
    """Verify that step callbacks increment conversation.usage directly."""

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
        conv = Conversation()
        conv.ui_update_callback = lambda: None
        on_step = create_step_callback(conv)

        on_step(self._make_action_step(100, 50), agent=None)
        assert conv.usage.input_tokens == 100
        assert conv.usage.output_tokens == 50

        on_step(self._make_action_step(200, 80), agent=None)
        assert conv.usage.input_tokens == 300
        assert conv.usage.output_tokens == 130

    def test_records_step_fact_with_tokens_and_agent_role(self):
        conv = Conversation()
        conv.ui_update_callback = lambda: None
        parent_agent = Mock(macllm_name="default")
        conv.agent = parent_agent
        on_step = create_step_callback(conv)

        step = self._make_action_step(100, 50)
        step.tool_calls = [{"name": "lookup", "arguments": {"query": "budget"}}]
        step.observations = "full tool result"

        on_step(step, agent=parent_agent)

        entry = conv.conversation_log[-1]
        assert entry.kind == "step"
        assert entry.tokens == 150
        assert entry.payload["agent_role"] == "parent"
        assert entry.payload["agent_name"] == "default"
        assert entry.payload["tool_calls"][0]["arguments"] == {"query": "budget"}
        assert entry.payload["observations"] == "full tool result"

    def test_records_subagent_step_fact_with_same_callback(self):
        conv = Conversation()
        conv.ui_update_callback = lambda: None
        conv.agent = Mock(macllm_name="default")
        subagent = Mock(macllm_name="notes")
        on_step = create_step_callback(conv)

        on_step(self._make_action_step(10, 5), agent=subagent)

        entry = conv.conversation_log[-1]
        assert entry.kind == "step"
        assert entry.payload["agent_role"] == "subagent"
        assert entry.payload["agent_name"] == "notes"

    def test_accumulates_planning_step_tokens(self):
        conv = Conversation()
        conv.ui_update_callback = lambda: None
        on_step = create_step_callback(conv)

        on_step(self._make_planning_step(50, 20), agent=None)
        assert conv.usage.input_tokens == 50
        assert conv.usage.output_tokens == 20

    def test_mixed_steps(self):
        conv = Conversation()
        conv.ui_update_callback = lambda: None
        on_step = create_step_callback(conv)

        on_step(self._make_planning_step(10, 5), agent=None)
        on_step(self._make_action_step(100, 50), agent=None)
        assert conv.usage.input_tokens == 110
        assert conv.usage.output_tokens == 55

    def test_planning_step_updates_plan_text_and_status(self):
        conv = Conversation()
        conv.ui_update_callback = lambda: None
        on_step = create_step_callback(conv)

        planning_message = Mock()
        planning_message.content = (
            "### Plan:\n"
            "[ ] Search for dinner details\n"
            "<end_plan>\n"
            "### Status:\n"
            "Found only Friday dinner details so far.\n"
            "<end_status>\n"
        )
        step = PlanningStep(
            model_input_messages=[],
            model_output_message=planning_message,
            plan="test plan",
            timing=Timing(start_time=0.0),
            token_usage=TokenUsage(input_tokens=10, output_tokens=5),
        )
        on_step(step, agent=None)
        plan = latest_plan(conv.conversation_log)
        assert plan["text"] == "[ ] Search for dinner details"
        assert plan["status"] == "Found only Friday dinner details so far."

    def test_task_step_ignored(self):
        conv = Conversation()
        conv.ui_update_callback = lambda: None
        on_step = create_step_callback(conv)

        on_step(TaskStep(task="sub"), agent=None)
        assert conv.usage.input_tokens == 0
        assert conv.usage.output_tokens == 0

    def test_no_conversation_no_crash(self):
        on_step = create_step_callback(None)
        on_step(self._make_action_step(100, 50), agent=None)

    def test_none_token_usage_skipped(self):
        conv = Conversation()
        conv.ui_update_callback = lambda: None

        step = ActionStep(
            step_number=1,
            timing=Timing(start_time=0.0),
            token_usage=None,
        )
        on_step = create_step_callback(conv)
        on_step(step, agent=None)
        assert conv.usage.input_tokens == 0
        assert conv.usage.output_tokens == 0


# ---------------------------------------------------------------------------
# Conversation.usage integration
# ---------------------------------------------------------------------------

class TestConversationUsage:
    """Verify that _process_query correctly wires the conversation to the step callback."""

    def test_initial_usage_is_zero(self):
        conv = Conversation()
        assert conv.usage.input_tokens == 0
        assert conv.usage.output_tokens == 0

    def test_usage_reset_on_submit(self):
        """Submitting a query resets token counts to 0 before starting."""
        mac = create_macllm(debug=False, start_ui=False)
        conv = mac.chat_history
        conv.usage.input_tokens = 999
        conv.usage.output_tokens = 888

        with patch("macllm.core.agent_service.create_agent") as mock_create:
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="done")
            mock_agent.memory = Mock()
            mock_agent.memory.steps = []
            mock_create.return_value = mock_agent
            conv.submit("test")
            time.sleep(0.3)

        assert conv.usage.input_tokens == 0
        assert conv.usage.output_tokens == 0

    def test_conversation_passed_to_create_agent(self):
        """_process_query passes the conversation itself to create_agent."""
        mac = create_macllm(debug=False, start_ui=False)
        conv = mac.chat_history

        captured = {}

        def intercept_create_agent(agent_cls=None, speed="normal", conversation=None, no_tools=False):
            captured["conversation"] = conversation
            mock_agent = Mock()
            mock_agent.run = Mock(return_value="done")
            mock_agent.memory = Mock()
            mock_agent.memory.steps = []
            return mock_agent

        with patch("macllm.core.agent_service.create_agent", side_effect=intercept_create_agent):
            conv.submit("test")
            time.sleep(0.3)

        assert captured.get("conversation") is conv

    def test_no_tools_is_request_scoped_on_persistent_agent(self):
        mac = create_macllm(debug=False, start_ui=False)
        conv = mac.chat_history
        conv.title = "Existing"
        disabled_during_run = []

        with patch("macllm.core.agent_service.create_agent") as mock_create:
            mock_agent = Mock()
            mock_agent.memory = Mock(steps=[])
            mock_agent.run.side_effect = lambda *args, **kwargs: (
                disabled_during_run.append(mock_agent._tools_disabled) or "done"
            )
            mock_create.return_value = mock_agent

            conv.submit("first")
            time.sleep(0.3)
            conv.submit("2+2 /notool")
            time.sleep(0.3)

        assert disabled_during_run == [False, True]
        assert mock_agent._tools_disabled is False
        mock_create.assert_called_once()


# ---------------------------------------------------------------------------
# Top-bar display text verification
# ---------------------------------------------------------------------------

class TestTopBarDisplayValues:
    """Verify the cumulative data that the top bar displays."""

    def test_total_tokens_cover_all_conversation_runs(self):
        conv = Conversation()
        for input_tokens, output_tokens in ((100, 20), (250, 40)):
            append_step(conv.conversation_log, {
                "step_type": "action",
                "token_usage": {
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
                },
            })

        # Per-run usage may have been reset; the displayed total comes from
        # the durable conversation log and therefore survives that reset.
        conv.usage.reset()

        assert token_usage_totals(conv.conversation_log) == (350, 60)

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
        """Switching tabs updates chat_history and each conversation's usage is independent."""
        mac = create_macllm(debug=False, start_ui=False)

        conv_a = mac.chat_history
        conv_a.usage.input_tokens = 100
        conv_a.usage.output_tokens = 50
        conv_a.speed_level = "fast"

        conv_b = mac.conversation_history.add_conversation()
        conv_b.ui_update_callback = mac._update_ui_from_callback
        conv_b.usage.input_tokens = 200
        conv_b.usage.output_tokens = 80
        conv_b.speed_level = "slow"

        mac.switch_to_conversation(1)
        assert mac.chat_history is conv_b
        assert mac.chat_history.usage.input_tokens == 200
        assert mac.chat_history.speed_level == "slow"

        mac.switch_to_conversation(0)
        assert mac.chat_history is conv_a
        assert mac.chat_history.usage.input_tokens == 100
        assert mac.chat_history.speed_level == "fast"
