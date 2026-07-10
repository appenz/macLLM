"""Tests for minimal source identity records on Conversation."""

from macllm.core.chat_history import Conversation


def test_add_source_stores_kind_and_ref_only():
    conv = Conversation()
    conv.add_source("file", "/tmp/notes/todo.md")
    assert conv.sources == [{"kind": "file", "ref": "/tmp/notes/todo.md"}]


def test_add_source_dedupes_and_moves_to_end():
    conv = Conversation()
    conv.add_source("file", "/tmp/a.txt")
    conv.add_source("web", "https://example.com")
    conv.add_source("file", "/tmp/a.txt")
    assert [s["kind"] for s in conv.sources] == ["web", "file"]
    assert conv.sources[-1]["ref"] == "/tmp/a.txt"


def test_add_source_keeps_caller_ref_as_given():
    conv = Conversation()
    conv.add_source("clipboard", "clipboard")
    assert conv.sources == [{"kind": "clipboard", "ref": "clipboard"}]
