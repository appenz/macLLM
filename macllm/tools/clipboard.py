"""Clipboard tool: read current pasteboard text or image."""

from __future__ import annotations

import macllm.macllm as macllm_app

from macllm.core.chat_history import add_source
from macllm.tools._debug import macllm_tool, set_tool_message


@macllm_tool
def read_clipboard() -> str:
    """
    Read the current macOS clipboard.

    Returns text when the clipboard contains text, or an image observation when
    it contains an image. Call this when the user refers to the clipboard.
    """
    set_tool_message("Reading clipboard")
    ui = getattr(macllm_app.MacLLM._instance, "ui", None)
    if ui is None:
        return "Error: Clipboard is unavailable."

    text = ui.read_clipboard()
    if text is not None:
        add_source("clipboard", "clipboard")
        return text

    image = ui.read_clipboard_image()
    if image is not None:
        add_source("clipboard", "clipboard")
        return image

    return "Error: Clipboard is empty."
