"""Visual regression UI tests for macLLM.

These tests open the real macLLM window, submit queries to a real LLM,
capture screenshots, and verify visual properties using a vision-capable
LLM.  They require API keys to be configured.

Run with: make test-ui-external
"""

import pytest

from macllm.ui.main_text import MainTextHandler


def _skip_if_no_api_keys():
    from macllm.core.config import get_runtime_config
    cfg = get_runtime_config()
    if not cfg.api_keys.openai and not cfg.api_keys.gemini:
        pytest.skip("No API keys configured -- skipping uitest_external")


@pytest.mark.uitest_external
def test_one_plus_one_shows_two(ui, tmp_path):
    """Submit '1+1' and verify the window screenshot contains '2'."""
    _skip_if_no_api_keys()

    ui.type_text("What is 1+1? Answer with just the number.")
    ui.press_key("return")

    # Wait for the agent to finish (background thread)
    app = ui._ui.macllm
    done = ui.wait_for(
        lambda: (
            not app.chat_history.is_agent_running()
            and len(MainTextHandler.displayable_messages(app.chat_history)) >= 3
        ),
        timeout=30.0,
        interval=0.5,
    )
    assert done, "Agent did not complete within 30 seconds"

    # Let the UI render the response
    ui.spin(1.0)

    # Functional check: the answer should contain "2"
    assert "2" in ui.conversation_text()

    # Visual check: screenshot should show "2" in the window
    path = str(tmp_path / "one_plus_one.png")
    assert ui.screenshot(path), "Failed to capture screenshot"
    assert ui.check_screenshot(path, "The window shows the number 2 as an answer")
