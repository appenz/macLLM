from macllm.core.chat_history import Conversation
from macllm.core.conversation_log import (
    ConversationLog,
    ConversationLogEntry,
    add_tool_call,
    append_activity_marker,
    append_run_end,
    append_run_start,
    append_step,
    clear_activity_markers,
    log_from_messages,
    message,
    messages_from_log,
    persistable_log,
    update_last_tool_message,
)


def test_message_entry_preserves_payload_copy():
    payload = {"role": "user", "content": "hello"}
    entry = message(payload["role"], payload["content"])
    payload["content"] = "mutated"

    assert isinstance(entry, ConversationLogEntry)
    assert entry.kind == "message"
    assert entry.payload == {"role": "user", "content": "hello"}


def test_messages_round_trip_through_log():
    messages = [
        {"role": "system", "content": "sys"},
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]

    log = log_from_messages(messages)

    assert isinstance(log, ConversationLog)
    assert messages_from_log(log) == messages


def test_persistable_log_preserves_entry_timestamp():
    entry = message("user", "hello")
    entry.timestamp = 123.0

    stable = persistable_log([entry])

    assert stable[0].timestamp == 123.0
    assert stable[0].payload == {"role": "user", "content": "hello"}


def test_conversation_displayable_messages_come_from_log():
    conv = Conversation()
    conv.add_user_message("hello")
    conv.add_assistant_message("hi")

    assert [
        m for m in messages_from_log(conv.conversation_log)
        if m["role"] in ("user", "assistant")
    ] == [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": "hi"},
    ]


def test_tool_call_entries_store_simple_log_payloads():
    log = ConversationLog()

    add_tool_call(log, "search_notes", "Using tool: search_notes")
    update_last_tool_message(log, 'Searching notes for "budget"')

    assert log[0].kind == "tool_call"
    assert log[0].payload == {
        "tool": "search_notes",
        "message": 'Searching notes for "budget"',
    }


def test_activity_markers_are_minimal_transient_entries():
    log = ConversationLog()
    append_activity_marker(log, "planning_started", "default")
    append_activity_marker(log, "action_started", "notes")

    assert [(item.kind, item.payload) for item in log] == [
        ("planning_started", "default"),
        ("action_started", "notes"),
    ]
    assert persistable_log(log) == []

    clear_activity_markers(log)
    assert log == []


def test_runtime_fact_entries_are_persistable():
    log = ConversationLog()

    append_run_start(log, {"query": "hello", "expanded_prompt": "hello expanded"})
    append_step(log, {
        "agent_name": "default",
        "agent_role": "parent",
        "step_type": "action",
        "tool_calls": [{"name": "search", "arguments": {"query": "hello"}}],
        "observations": "verbatim result",
        "token_usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
    }, tokens=15)
    append_run_end(log, {"status": "success", "elapsed_seconds": 1.25, "total_tokens": 15})

    stable = persistable_log(log)

    assert [item.kind for item in stable] == ["run_start", "step", "run_end"]
    assert stable[1].tokens == 15
    assert stable[1].payload["observations"] == "verbatim result"
