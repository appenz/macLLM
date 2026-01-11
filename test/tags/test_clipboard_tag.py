import pytest
from macllm.ui.core import MacLLMUI
from macllm.ui.input_field import InputFieldHandler
from test.conftest import get_context_blocks_from_messages


def test_clipboard_tag_plugin_loaded(app_mocked):
    assert any(p.__class__.__name__ == "ClipboardTag" for p in app_mocked.plugins)


def test_clipboard_tag_context_block(app_mocked):
    app_mocked.ui.read_clipboard = lambda: "TEST_TOKEN"
    
    # Mock agent.run to capture the expanded prompt
    expanded_prompts = []
    original_run = app_mocked.chat_history.agent.run
    
    def mock_run(prompt, **kwargs):
        expanded_prompts.append(prompt)
        return "MOCK_RESPONSE"
    
    app_mocked.chat_history.agent.run = mock_run
    
    app_mocked.handle_instructions("Summarize the text in @clipboard")
    
    # Wait for agent thread
    import time
    time.sleep(0.1)
    
    assert len(expanded_prompts) > 0, "Agent should have been called"
    
    # Check that expanded prompt contains clipboard content
    expanded = expanded_prompts[0]
    assert "TEST_TOKEN" in expanded, f"Expanded prompt should contain clipboard content, got: {expanded[:200]}"


@pytest.mark.external
def test_clipboard_tag_real(app_real):
    app_real.ui.read_clipboard = lambda: "What is 1+1? Answer only with a number."
    app_real.handle_instructions("Answer the question in @clipboard")
    
    # Wait for agent to complete
    import time
    max_wait = 10
    waited = 0
    while waited < max_wait:
        if app_real.chat_history.agent_status == "" and len(app_real.chat_history.messages) > 0:
            last_msg = app_real.chat_history.messages[-1]
            if last_msg['role'] == 'assistant':
                response = last_msg['content']
                assert "2" in response
                return
        time.sleep(0.5)
        waited += 0.5
    
    assert False, "Agent did not complete within timeout"
