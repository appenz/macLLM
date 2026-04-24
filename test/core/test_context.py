"""Registry-based and thread-local resolution for get_current_conversation."""

import threading

from macllm.core.context import (
    get_current_conversation,
    set_current_conversation,
    register_conversation,
    unregister_conversation,
    _thread_context,
    _registry,
)


class StubConv:
    def __init__(self, conv_id="test-id"):
        self.conv_id = conv_id
        self.agent_thread = None


class DummyApp:
    def __init__(self, *, chat_history):
        self.chat_history = chat_history


def _cleanup():
    _thread_context.conversation = None
    _registry.clear()


def test_explicit_conv_id_resolves_from_registry():
    conv = StubConv("abc")
    register_conversation(conv)
    try:
        assert get_current_conversation("abc") is conv
    finally:
        _cleanup()


def test_unknown_conv_id_falls_through_to_thread_local():
    tl = StubConv("tl")
    set_current_conversation(tl)
    try:
        assert get_current_conversation("unknown") is tl
    finally:
        _cleanup()


def test_thread_local_used_when_no_conv_id():
    tl = StubConv("tl")
    set_current_conversation(tl)
    try:
        assert get_current_conversation() is tl
    finally:
        _cleanup()


def test_registry_preferred_over_thread_local_when_conv_id_given():
    reg = StubConv("reg")
    tl = StubConv("tl")
    register_conversation(reg)
    set_current_conversation(tl)
    try:
        assert get_current_conversation("reg") is reg
    finally:
        _cleanup()


def test_fallback_to_chat_history():
    from macllm.macllm import MacLLM

    fallback = StubConv("fb")
    MacLLM._instance = DummyApp(chat_history=fallback)
    _thread_context.conversation = None
    try:
        assert get_current_conversation() is fallback
    finally:
        MacLLM._instance = None
        _cleanup()


def test_unregister_removes_from_registry():
    conv = StubConv("rm")
    register_conversation(conv)
    unregister_conversation(conv)
    assert "rm" not in _registry
    _cleanup()
