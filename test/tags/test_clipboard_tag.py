import pytest
from macllm.ui.core import MacLLMUI
from macllm.ui.input_field import InputFieldHandler
from test.conftest import get_context_blocks_from_messages


def test_clipboard_tag_plugin_loaded(app_mocked):
    assert any(p.__class__.__name__ == "ClipboardTag" for p in app_mocked.plugins)


def test_clipboard_tag_context_block(app_mocked):
    app_mocked.ui.read_clipboard = lambda: "TEST_TOKEN"
    app_mocked.handle_instructions("Summarize the text in @clipboard")

    assert app_mocked._llm_mock.called
    
    call_args = app_mocked._llm_mock.call_args
    messages = call_args.args[0] if call_args.args else call_args.kwargs.get('messages', [])
    
    ctx = get_context_blocks_from_messages(messages)
    assert "clipboard" in ctx
    assert "TEST_TOKEN" in ctx["clipboard"]


@pytest.mark.external
def test_clipboard_tag_real(app_real):
    app_real.ui.read_clipboard = lambda: "What is 1+1? Answer only with a number."
    response = app_real.handle_instructions("Answer the question in @clipboard")
    assert response == "2"
