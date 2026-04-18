"""Functional UI tests for macLLM.

These tests open the real macLLM window and drive it via the UITestDriver.
They assert on Cocoa object state (text content, window visibility, etc.)
and do NOT call external APIs.

Run with: make test-ui
"""

import pytest


@pytest.mark.uitest
def test_type_text(ui):
    """Typing text appears in the input field."""
    ui.type_text("Hello world")
    assert ui.input_text() == "Hello world"


@pytest.mark.uitest
def test_escape_closes_window(ui):
    """Pressing Escape closes the window."""
    assert ui.window_open()
    ui.press_key("escape")
    ui.spin(0.3)
    assert not ui.window_open()


@pytest.mark.uitest
def test_window_initial_state(ui):
    """Window opens with empty input and an empty conversation area."""
    assert ui.window_open()
    assert ui.input_text() == ""
    assert ui.conversation_text().strip() == ""


@pytest.mark.uitest
def test_screenshot_capture(ui, tmp_path):
    """Screenshot captures a PNG file of the window."""
    path = str(tmp_path / "test_capture.png")
    assert ui.screenshot(path)
    import os
    assert os.path.exists(path)
    assert os.path.getsize(path) > 0
