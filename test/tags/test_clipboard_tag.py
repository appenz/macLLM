import pytest
from unittest.mock import Mock, patch
from macllm.ui.core import MacLLMUI
from macllm.ui.input_field import InputFieldHandler

def test_clipboard_tag_plugin_loaded(app_fake):
    # plugin loaded?
    assert any(p.__class__.__name__ == "ClipboardTag" for p in app_fake.plugins)

def test_clipboard_tag_context_block(app_fake):
    # fake clipboard
    app_fake.ui.read_clipboard = lambda: "TEST_TOKEN"
    app_fake.handle_instructions("Summarize the text in @clipboard")

    # ensure prompt recorded by fake connector contains context block
    ctx = app_fake.llm.get_context_blocks()
    assert "clipboard" in ctx
    assert "TEST_TOKEN" in ctx["clipboard"]


# External end-to-end example (skipped unless OPENAI_API_KEY set)


@pytest.mark.external
def test_clipboard_tag_real(app_real):
    app_real.ui.read_clipboard = lambda: "What is 1+1? Answer only with a number."
    response = app_real.handle_instructions("Answer the question in @clipboard")
    assert response == "2"



