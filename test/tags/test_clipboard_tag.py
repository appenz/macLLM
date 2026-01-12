import time
import pytest
from unittest.mock import Mock, patch
from macllm.ui.core import MacLLMUI
from macllm.ui.input_field import InputFieldHandler
from test.conftest import get_context_blocks_from_messages


def test_clipboard_tag_plugin_loaded(app_mocked):
    assert any(p.__class__.__name__ == "ClipboardTag" for p in app_mocked.plugins)


class MockAgentMemory:
    def __init__(self):
        self.steps = []


class MockAgent:
    def __init__(self, run_callback=None):
        self.memory = MockAgentMemory()
        self._run_callback = run_callback
    
    def run(self, prompt, **kwargs):
        if self._run_callback:
            self._run_callback(prompt)
        return "MOCK_RESPONSE"


def test_clipboard_tag_context_block(app_mocked, monkeypatch):
    app_mocked.ui.read_clipboard = lambda: "TEST_TOKEN"
    
    expanded_prompts = []
    
    def capture_prompt(prompt):
        expanded_prompts.append(prompt)
    
    mock_agent = MockAgent(run_callback=capture_prompt)
    
    from macllm.core import agent_service
    monkeypatch.setattr(agent_service, 'create_agent', lambda **kwargs: mock_agent)
    
    app_mocked.handle_instructions("Summarize the text in @clipboard")
    
    time.sleep(0.1)
    
    assert len(expanded_prompts) > 0, "Agent should have been called"
    
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
