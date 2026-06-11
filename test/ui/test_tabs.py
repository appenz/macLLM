"""Tests for conversation tab bar.

Functional tests (uitest) verify tab creation, switching, keyboard
navigation, and close button.  External tests (uitest_external) verify
title generation via LLM.

Run with: make test-ui            (functional)
          make test-ui-external   (visual)
"""

import pytest


# ---------------------------------------------------------------------------
# Functional tests (no API keys needed)
# ---------------------------------------------------------------------------

@pytest.mark.uitest
def test_tab_bar_exists_with_single_conversation(ui):
    """Even with one conversation, the tab bar renders one tab."""
    assert ui.tab_count() == 1


@pytest.mark.uitest
def test_initial_title_is_new(ui):
    """A fresh conversation tab shows 'New'."""
    assert ui.active_tab_title() == "New Agent"


@pytest.mark.uitest
def test_new_conversation_shows_tab(ui):
    """Creating a new conversation adds a second tab."""
    assert ui.tab_count() == 1
    ui.new_conversation()
    ui.spin(0.3)
    assert ui.tab_count() == 2


@pytest.mark.uitest
def test_tab_count_after_multiple_new(ui):
    """Creating 3 new conversations results in 4 total tabs."""
    assert ui.tab_count() == 1
    for _ in range(3):
        ui.new_conversation()
        ui.spin(0.1)
    assert ui.tab_count() == 4


@pytest.mark.uitest
def test_active_tab_is_newest(ui):
    """After new_conversation the active conversation is the newest one."""
    ui.new_conversation()
    ui.spin(0.3)
    assert ui.active_tab_title() == "New Agent"
    assert ui.conversation_text().strip() == ""


@pytest.mark.uitest
def test_new_conversation_preserves_original_tab_draft(ui):
    """Creating a new tab preserves draft input in the original tab."""
    ui.type_text("partial request")
    ui.new_conversation()
    ui.spin(0.3)
    assert ui.input_text() == ""

    ui._ui.switch_conversation(0)
    ui.spin(0.3)
    assert ui.input_text() == "partial request"


# ---------------------------------------------------------------------------
# Ctrl+Tab / Ctrl+Shift+Tab navigation (newest-left tab ordering)
#
# Tab bar shows newest on the left, so:
#   Ctrl+Tab       → next older conversation (rightward, delta -1)
#   Ctrl+Shift+Tab → next newer conversation (leftward, delta +1)
# ---------------------------------------------------------------------------

@pytest.mark.uitest
def test_ctrl_tab_goes_to_older(ui):
    """Ctrl+Tab moves to the older (rightward) conversation."""
    ui.new_conversation()
    ui.spin(0.3)
    app = ui._ui.macllm
    assert app.conversation_history.active_index == 1

    ui.press_ctrl_tab()
    ui.spin(0.3)
    assert app.conversation_history.active_index == 0


@pytest.mark.uitest
def test_ctrl_shift_tab_goes_to_newer(ui):
    """Ctrl+Shift+Tab moves back to the newer (leftward) conversation."""
    ui.new_conversation()
    ui.spin(0.3)
    app = ui._ui.macllm

    ui.press_ctrl_tab()
    ui.spin(0.3)
    assert app.conversation_history.active_index == 0

    ui.press_ctrl_shift_tab()
    ui.spin(0.3)
    assert app.conversation_history.active_index == 1


@pytest.mark.uitest
def test_ctrl_tab_preserves_per_tab_drafts(ui):
    """Keyboard tab cycling preserves each tab's draft input."""
    ui.type_text("older draft")
    ui.new_conversation()
    ui.spin(0.3)
    ui.type_text("newer draft")

    ui.press_ctrl_tab()
    ui.spin(0.3)
    assert ui.input_text() == "older draft"

    ui.press_ctrl_shift_tab()
    ui.spin(0.3)
    assert ui.input_text() == "newer draft"


@pytest.mark.uitest
def test_ctrl_shift_tab_at_newest_is_noop(ui):
    """At the newest conversation, Ctrl+Shift+Tab does nothing."""
    ui.new_conversation()
    ui.spin(0.3)
    app = ui._ui.macllm
    assert app.conversation_history.active_index == 1
    ui.press_ctrl_shift_tab()
    ui.spin(0.2)
    assert app.conversation_history.active_index == 1


@pytest.mark.uitest
def test_ctrl_tab_at_oldest_is_noop(ui):
    """At the oldest conversation, Ctrl+Tab does nothing."""
    app = ui._ui.macllm
    assert app.conversation_history.active_index == 0
    ui.press_ctrl_tab()
    ui.spin(0.2)
    assert app.conversation_history.active_index == 0


# ---------------------------------------------------------------------------
# Click switching tests
# ---------------------------------------------------------------------------

@pytest.mark.uitest
def test_switch_conversation_via_ui(ui):
    """Calling switch_conversation directly changes the active tab."""
    ui.new_conversation()
    ui.spin(0.3)
    app = ui._ui.macllm
    assert app.conversation_history.active_index == 1

    ui._ui.switch_conversation(0)
    ui.spin(0.3)
    assert app.conversation_history.active_index == 0


@pytest.mark.uitest
def test_switch_updates_text_area(ui):
    """Switching conversations updates the conversation text area."""
    app = ui._ui.macllm
    app.chat_history.add_user_message("hello from conv 0")
    ui.new_conversation()
    ui.spin(0.3)

    text_conv1 = ui.conversation_text()
    ui._ui.switch_conversation(0)
    ui.spin(0.3)
    text_conv0 = ui.conversation_text()
    assert "hello from conv 0" in text_conv0
    assert "hello from conv 0" not in text_conv1


# ---------------------------------------------------------------------------
# Close button / Cmd+W tests
# ---------------------------------------------------------------------------

@pytest.mark.uitest
def test_close_only_conversation_creates_new(ui):
    """Closing the only conversation creates a fresh one."""
    app = ui._ui.macllm
    assert ui.tab_count() == 1
    ui.close_conversation(0)
    ui.spin(0.3)
    assert ui.tab_count() == 1
    assert ui.active_tab_title() == "New Agent"


@pytest.mark.uitest
def test_close_inactive_conversation(ui):
    """Closing a non-active tab removes it without changing active."""
    ui.new_conversation()
    ui.spin(0.1)
    ui.new_conversation()
    ui.spin(0.1)
    app = ui._ui.macllm
    assert ui.tab_count() == 3
    assert app.conversation_history.active_index == 2

    ui.close_conversation(0)
    ui.spin(0.3)
    assert ui.tab_count() == 2
    assert app.conversation_history.active_index == 1


@pytest.mark.uitest
def test_close_active_conversation(ui):
    """Closing the active tab switches to an adjacent conversation."""
    ui.new_conversation()
    ui.spin(0.1)
    app = ui._ui.macllm
    assert app.conversation_history.active_index == 1

    ui.close_conversation(1)
    ui.spin(0.3)
    assert ui.tab_count() == 1
    assert app.conversation_history.active_index == 0


@pytest.mark.uitest
def test_cmd_w_closes_active_tab(ui):
    """Cmd+W closes the active conversation tab."""
    ui.new_conversation()
    ui.spin(0.3)
    app = ui._ui.macllm
    assert ui.tab_count() == 2

    ui.close_active_tab()
    ui.spin(0.3)
    assert ui.tab_count() == 1


# ---------------------------------------------------------------------------
# External test (requires API keys)
# ---------------------------------------------------------------------------

def _skip_if_no_api_keys():
    from macllm.core.config import get_runtime_config
    cfg = get_runtime_config()
    if not cfg.api_keys.openai and not cfg.api_keys.gemini:
        pytest.skip("No API keys configured -- skipping uitest_external")


@pytest.mark.uitest_external
def test_title_changes_after_query(ui):
    """After submitting a query the conversation title must change from 'New'."""
    _skip_if_no_api_keys()

    ui.type_text("What is 1+1? Answer with just the number.")
    ui.press_key("return")

    app = ui._ui.macllm
    done = ui.wait_for(
        lambda: not app.chat_history.is_agent_running() and len(app.chat_history.messages) >= 3,
        timeout=30.0,
        interval=0.5,
    )
    assert done, "Agent did not complete within 30 seconds"
    ui.spin(3.0)

    assert app.chat_history.title != "New", (
        f"Title should change from 'New' but is still: {app.chat_history.title!r}"
    )
