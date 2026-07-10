import time
import pytest
from unittest.mock import Mock
from macllm.core.user_request import UserRequest
from macllm.tags.clipboard_tag import ClipboardTag


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
            self._run_callback(prompt, **kwargs)
        return "MOCK_RESPONSE"


def test_clipboard_tag_rewrites_to_tool_instruction(app_mocked, monkeypatch):
    expanded_prompts = []

    def capture_prompt(prompt, **kwargs):
        expanded_prompts.append(prompt)

    mock_agent = MockAgent(run_callback=capture_prompt)

    from macllm.core import agent_service
    monkeypatch.setattr(agent_service, 'create_agent', lambda **kwargs: mock_agent)

    # Clipboard must not be read during tag expansion.
    app_mocked.ui.read_clipboard = Mock(side_effect=AssertionError("tag must not read clipboard"))
    app_mocked.ui.read_clipboard_image = Mock(side_effect=AssertionError("tag must not read clipboard"))

    app_mocked.chat_history.submit("Summarize the text in @clipboard")
    time.sleep(0.1)

    assert len(expanded_prompts) > 0
    expanded = expanded_prompts[0]
    assert "read_clipboard()" in expanded
    assert "TEST_TOKEN" not in expanded
    assert "--- context:" not in expanded


def test_clipboard_tag_expand_unit():
    tag = ClipboardTag(Mock())
    result = tag.expand("@clipboard", Mock(), UserRequest("x"))
    assert result == "Clipboard (use read_clipboard())"


def test_clipboard_tag_does_not_pass_images(app_mocked, monkeypatch):
    captured_kwargs = []

    def capture_prompt(prompt, **kwargs):
        captured_kwargs.append(kwargs)

    mock_agent = MockAgent(run_callback=capture_prompt)

    from macllm.core import agent_service
    monkeypatch.setattr(agent_service, 'create_agent', lambda **kwargs: mock_agent)

    app_mocked.chat_history.submit("Describe @clipboard")
    time.sleep(0.1)

    assert len(captured_kwargs) > 0
    assert "images" not in captured_kwargs[0]
