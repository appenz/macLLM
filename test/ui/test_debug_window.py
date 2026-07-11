from macllm.core.chat_history import Conversation
from macllm.core.conversation_log import (
    append_activity_marker,
    append_plan,
    append_run_start,
    append_step,
    message,
)
from macllm.ui.debug_window import extract_cards


def test_step_card_body_hides_runtime_metadata():
    conv = Conversation()
    append_step(conv.conversation_log, {
        "agent_name": "default",
        "agent_role": "parent",
        "step_type": "action",
        "step_number": 1,
        "token_usage": {
            "input_tokens": 10,
            "output_tokens": 5,
            "total_tokens": 15,
        },
        "timing": {
            "start_time": 1.0,
            "end_time": 2.0,
            "duration": 1.0,
        },
        "model_output": "I will call a tool.",
        "tool_calls": [{
            "name": "lookup",
            "arguments": {"query": "budget"},
            "id": "abc",
        }],
        "observations": "lookup result",
    }, tokens=15)

    card = extract_cards(conv)[0]

    assert card.title == "Tool Call: lookup"
    assert card.step_tokens == "10 in / 5 out"
    assert card.total_tokens == "10 in / 5 out"
    assert card.step_time == "1.00s"
    assert "LLM response" in card.body
    assert "Tool call 1: lookup" in card.body
    assert "query: budget" in card.body
    assert "Tool result" in card.body
    assert "agent_name" not in card.body
    assert "agent_role" not in card.body
    assert "step_type" not in card.body
    assert "token_usage" not in card.body
    assert "start_time" not in card.body


def test_activity_markers_are_not_debug_cards():
    conv = Conversation()
    append_activity_marker(conv.conversation_log, "planning_started", "default")
    append_activity_marker(conv.conversation_log, "action_started", "default")

    assert extract_cards(conv) == []


def _append_turn(conv: Conversation, raw: str, expanded: str, plan: str, answer: str):
    conv.conversation_log.append(message("user", raw))
    append_run_start(conv.conversation_log, {
        "query": raw,
        "expanded_prompt": expanded,
    })
    append_step(conv.conversation_log, {
        "agent_name": "default",
        "agent_role": "parent",
        "step_type": "planning",
        "token_usage": {"input_tokens": 10, "output_tokens": 2, "total_tokens": 12},
        "timing": {"duration": 0.5},
        "model_output": f"### Plan:\n{plan}",
        "plan": plan,
    }, tokens=12)
    append_plan(conv.conversation_log, text=plan, status="working")
    append_step(conv.conversation_log, {
        "agent_name": "default",
        "agent_role": "parent",
        "step_type": "action",
        "token_usage": {"input_tokens": 20, "output_tokens": 5, "total_tokens": 25},
        "timing": {"duration": 1.0},
        "tool_calls": [{
            "name": "final_answer",
            "arguments": {"answer": answer},
        }],
    }, tokens=25)
    conv.conversation_log.append(message("assistant", answer))


def test_extract_cards_dedupes_each_request_independently():
    conv = Conversation()
    _append_turn(
        conv,
        raw="first question",
        expanded="first question",
        plan="[ ] answer first",
        answer="first answer",
    )
    _append_turn(
        conv,
        raw="second question",
        expanded="second question with context",
        plan="[ ] answer second",
        answer="second answer",
    )

    cards = extract_cards(conv)

    assert [card.title for card in cards] == [
        "User Request",
        "Planning Step",
        "Assistant Response",
        "User Request",
        "Planning Step",
        "Assistant Response",
    ]
    assert cards[0].body == "first question"
    assert "Expanded request" not in cards[0].body
    assert "Request:\nsecond question" in cards[3].body
    assert "Expanded request:\nsecond question with context" in cards[3].body
    assert cards[2].body == "first answer"
    assert cards[5].body == "second answer"
