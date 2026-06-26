from macllm.core.chat_history import Conversation
from macllm.core.conversation_log import (
    ConversationLog,
    ConversationLogEntry,
    log_from_messages,
    message,
    messages_from_log,
    persistable_log,
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
