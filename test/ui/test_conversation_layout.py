"""UI layout tests for the conversation text area."""

import pytest

from macllm.core.conversation_log import message


def _conversation_layout(ui):
    scroll_view = ui._ui.scroll_view
    text_view = ui._ui.text_area
    clip_width = scroll_view.contentView().bounds().size.width
    text_frame = text_view.frame()
    text_right_edge = text_frame.origin.x + text_frame.size.width
    container_width = None
    text_container = text_view.textContainer()
    if text_container is not None:
        container_width = text_container.containerSize().width
    return scroll_view, clip_width, text_right_edge, container_width


@pytest.mark.uitest
def test_conversation_text_fits_scroll_clip_width(ui):
    """Text should not extend beneath the vertical scrollbar."""
    conv = ui._ui.macllm.chat_history
    bullets = "\n".join(
        f"- list item {i} with enough words to wrap near the right edge"
        for i in range(12)
    )
    filler_lines = [
        f"Line {i}: trailing colon test: " + ("word " * 18)
        for i in range(180)
    ]
    conv.conversation_log.append(
        message(
            "assistant",
            "Intro paragraph before the list.\n\n"
            f"{bullets}\n\n**After list**\n\n"
            + "\n".join(filler_lines),
        )
    )
    ui._ui.update_window()
    ui.spin(0.3)

    scroll_view, clip_width, text_right_edge, container_width = _conversation_layout(ui)
    assert scroll_view.hasVerticalScroller(), "expected enough content to require scrolling"
    assert text_right_edge <= clip_width + 1.0
    if container_width is not None:
        assert container_width <= clip_width + 1.0
