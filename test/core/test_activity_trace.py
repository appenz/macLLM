from dataclasses import dataclass

from smolagents import ActionStep
from smolagents.memory import Timing

from macllm.core.abortable_model import AbortableModel
from macllm.core.activity_trace import ActivityTrace, crop_text, estimate_text_tokens
from macllm.core.agent_service import create_step_callback
from macllm.core.chat_history import Usage
from macllm.core.conversationlog import ConversationLog, current_activity_trace, start_activity_trace


@dataclass
class TokenUsage:
    input_tokens: int
    output_tokens: int


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def test_activity_trace_aggregates_self_and_total_metrics():
    clock = Clock()
    trace = ActivityTrace("default agent", clock=clock)

    planning = trace.start_model_call("Thinking")
    clock.advance(1.2)
    trace.finish_model_call(planning)
    trace.close_current_model_step(
        label="Planning",
        token_usage=TokenUsage(input_tokens=2000, output_tokens=700),
    )

    with trace.scoped_node("Calendar agent: Find Mike Smith's email", kind="agent"):
        clock.advance(0.5)
        search = trace.open_node('Search email: "Mike Smith"', kind="tool")
        clock.advance(2.0)
        trace.close_node(search)
        thinking = trace.start_model_call("Thinking")
        clock.advance(1.0)
        trace.finish_model_call(thinking)
        trace.close_current_model_step(
            token_usage=TokenUsage(input_tokens=1500, output_tokens=500),
        )

    trace.finish()

    root = trace.root
    calendar = root.children[1]
    assert root.total_tokens == 4700
    assert calendar.total_tokens == 2000
    assert calendar.self_tokens == 0
    assert calendar.total_time(clock()) == 3.5
    assert calendar.self_time(clock()) == 0.5


def test_model_invocation_row_exists_before_step_callback():
    clock = Clock()
    trace = ActivityTrace("default agent", clock=clock)

    node = trace.start_model_call("Thinking")
    clock.advance(0.4)
    trace.finish_model_call(node)

    lines = trace.format_ui_lines(width=60)
    assert any("Thinking" in line for line in lines)
    assert node.state == "running"

    trace.close_current_model_step(
        label="Planning",
        token_usage=TokenUsage(input_tokens=100, output_tokens=50),
    )

    lines = trace.format_ui_lines(width=60)
    assert any("Planning" in line and "150 tok" in line for line in lines)


def test_debug_summary_fits_sixty_columns_and_keeps_metrics():
    clock = Clock()
    trace = ActivityTrace("default agent", clock=clock)

    with trace.scoped_node(
        "Calendar agent: Find the email address for a very long person name",
        kind="agent",
    ):
        node = trace.start_model_call("Thinking about a very long execution step")
        clock.advance(4.5)
        trace.finish_model_call(node)
        trace.close_current_model_step(
            token_usage=TokenUsage(input_tokens=1800, output_tokens=200),
        )

    trace.finish()
    summary = trace.format_debug_summary(
        query="Add Mike Smith's email to the note foobar with a long query",
        width=60,
    )

    for line in summary.splitlines():
        assert len(line) <= 60
    assert "total" in summary or " t " in summary
    assert "..." in summary


def test_crop_text_middle_and_suffix_modes():
    assert crop_text("abcdefghijklmnopqrstuvwxyz", 10) == "abcdefg..."
    assert crop_text("abcdefghijklmnopqrstuvwxyz", 10, middle=True) == "abc...wxyz"


def test_final_answer_model_call_is_not_duplicated():
    class FakeFinalTool:
        name = "final_answer"

    class FakeModel:
        def generate(self, *args, **kwargs):
            return object()

    class FakeConversation:
        def __init__(self) -> None:
            self.conversation_log = ConversationLog()
            start_activity_trace(self.conversation_log, "default agent")._clock = Clock()
            self.usage = Usage()
            self.agent = None

        def _notify_ui(self) -> None:
            pass

        def clear_tool_calls(self) -> None:
            pass

    conv = FakeConversation()
    model = AbortableModel(FakeModel(), abort_event=type("Event", (), {
        "is_set": lambda self: False,
        "wait": lambda self, timeout: False,
    })(), conversation=conv)

    model.generate([], tools_to_call_from=[FakeFinalTool()])

    step = ActionStep(
        step_number=1,
        timing=Timing(start_time=0.0),
        token_usage=TokenUsage(input_tokens=3000, output_tokens=100),
    )
    step.is_final_answer = True
    step.observations = "done"

    create_step_callback(conv)(step, agent=None)

    trace = current_activity_trace(conv.conversation_log)
    final_nodes = [
        node for node in trace.root.children
        if node.label == "Final answer"
    ]
    assert len(final_nodes) == 1
    assert final_nodes[0].self_tokens == 3100


def test_seventy_two_column_debug_preserves_short_phase_labels_deep_in_tree():
    clock = Clock()
    trace = ActivityTrace("default agent", clock=clock)
    parent = trace.open_node("Notes agent: long task", kind="agent")
    child = trace.open_node("Email agent: long task", kind="agent")
    nested = trace.open_node("Final answer", kind="model")
    clock.advance(4.0)
    nested.add_tokens(TokenUsage(input_tokens=14000, output_tokens=900))
    trace.close_node(nested)
    trace.close_node(child)
    trace.close_node(parent)
    trace.finish()

    summary = trace.format_debug_summary(query="test", width=72)

    for line in summary.splitlines():
        assert len(line) <= 72
    assert any("Final answer" in line for line in summary.splitlines())


def test_debug_metrics_depend_on_node_kind():
    clock = Clock()
    trace = ActivityTrace("default agent", clock=clock)
    with trace.scoped_node("Calendar agent", kind="agent"):
        thinking = trace.open_node("Thinking", kind="model")
        thinking.add_tokens(TokenUsage(input_tokens=1200, output_tokens=300))
        tool = trace.open_node("Search calendar", kind="tool")
        clock.advance(0.8)
        trace.close_node(tool)
        trace.close_node(thinking)
    trace.finish()

    lines = trace.format_debug_summary(query="test", width=72).splitlines()
    agent_line = next(line for line in lines if "Calendar agent" in line)
    thinking_line = next(line for line in lines if "Thinking" in line)
    tool_line = next(line for line in lines if "Search calendar" in line)

    assert "total" in agent_line
    assert "self" not in agent_line
    assert "self" in thinking_line
    assert "total" not in thinking_line
    assert "self" in tool_line
    assert "total" not in tool_line


def test_tool_rows_show_result_token_estimate_when_present():
    clock = Clock()
    trace = ActivityTrace("default agent", clock=clock)
    tool = trace.open_node("Searching notes", kind="tool")
    trace.record_tool_result(tool, "abcd" * 100)
    clock.advance(0.2)
    trace.close_node(tool)
    trace.finish()

    summary = trace.format_debug_summary(query="test", width=72)

    assert "result 100/0.2s" in summary
    assert estimate_text_tokens("abcd" * 100) == 100
