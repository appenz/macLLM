"""UI test driver for macLLM.

Combines in-process keyboard injection (synthetic NSEvents + direct method
calls) with Quartz screenshot capture and optional vision-LLM regression
checks.  Designed to be driven by scripted tests or an interactive agent loop.
"""

from __future__ import annotations

import base64
import time
from typing import Callable

from Cocoa import (
    NSApplication,
    NSEvent,
    NSKeyDown,
    NSKeyUp,
    NSCommandKeyMask,
    NSShiftKeyMask,
    NSAlternateKeyMask,
    NSControlKeyMask,
    NSPasteboard,
    NSStringPboardType,
)
from Foundation import NSDate, NSRunLoop

from macllm.utils.screenshot import capture_window_by_title

# Virtual key codes (macOS HID key codes)
_KEY_CODES: dict[str, int] = {
    "return": 0x24,
    "tab": 0x30,
    "space": 0x31,
    "escape": 0x35,
    "delete": 0x33,
    "up": 0x7E,
    "down": 0x7D,
    "left": 0x7B,
    "right": 0x7C,
}

# Character-to-keycode mapping for printable keys used with modifiers
_CHAR_KEY_CODES: dict[str, int] = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04,
    "g": 0x05, "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09,
    "b": 0x0B, "q": 0x0C, "w": 0x0D, "e": 0x0E, "r": 0x0F,
    "y": 0x10, "t": 0x11, "1": 0x12, "2": 0x13, "3": 0x14,
    "4": 0x15, "5": 0x17, "6": 0x16, "7": 0x1A, "8": 0x1C,
    "9": 0x19, "0": 0x1D, "n": 0x2D, "m": 0x2E, "l": 0x25,
    "o": 0x1F, "p": 0x23, "i": 0x22, "u": 0x20, "k": 0x28,
    "j": 0x26,
}

# doCommandBySelector: selectors for named keys
_SELECTORS: dict[str, str] = {
    "return": "insertNewline:",
    "tab": "insertTab:",
    "escape": "cancelOperation:",
    "up": "moveUp:",
    "down": "moveDown:",
    "left": "moveLeft:",
    "right": "moveRight:",
    "delete": "deleteBackward:",
}


class UITestDriver:
    """Drive the macLLM UI via synthetic events and direct Cocoa calls."""

    def __init__(self, macllm_ui):
        """Wrap an already-started MacLLMUI instance."""
        self._ui = macllm_ui

    # ------------------------------------------------------------------
    # Actions – keyboard injection
    # ------------------------------------------------------------------

    def type_text(self, text: str) -> None:
        """Insert *text* into the currently focused input field."""
        self._ui.input_field.insertText_(text)
        self.spin(0.05)

    def press_key(self, name: str) -> None:
        """Press a named key (return, escape, tab, up, down, etc.).

        Calls the input field delegate's textView_doCommandBySelector_
        directly, which is the most reliable path.  For Return without
        Shift, currentEvent() is None/stale so the delegate treats it as
        a plain submit.  Use press_shift_key("return") for Shift-Return.
        """
        selector = _SELECTORS.get(name.lower())
        if selector is None:
            raise ValueError(f"Unknown key name: {name!r}")
        delegate = self._ui.window_delegate
        delegate.textView_doCommandBySelector_(self._ui.input_field, selector)
        self.spin(0.05)

    def press_cmd(self, key: str) -> None:
        """Press Cmd+<key> via a synthetic NSEvent."""
        self._post_key_event(key.lower(), modifier_mask=NSCommandKeyMask)
        self.spin(0.05)

    def new_conversation(self) -> None:
        """Create a new conversation (equivalent to Cmd+N)."""
        self._ui.macllm.new_conversation()
        from macllm.ui.input_field import InputFieldHandler
        InputFieldHandler.clear_input_field(self._ui.input_field)
        self._ui.update_window()
        self.spin(0.1)

    def close_conversation(self, index: int) -> None:
        """Close (delete) the conversation at *index*."""
        self._ui.close_conversation(index)
        self.spin(0.1)

    def close_active_tab(self) -> None:
        """Close the active conversation (equivalent to Cmd+W)."""
        active_idx = self._ui.macllm.conversation_history.active_index
        self._ui.close_conversation(active_idx)
        from macllm.ui.input_field import InputFieldHandler
        InputFieldHandler.clear_input_field(self._ui.input_field)
        self.spin(0.1)

    def press_shift_key(self, name: str) -> None:
        """Press Shift+<named key> via a synthetic NSEvent."""
        self._post_key_event(name.lower(), modifier_mask=NSShiftKeyMask)
        self.spin(0.05)

    def press_option(self, name: str) -> None:
        """Press Option+<named key> by calling the delegate with the
        corresponding word-movement selector (Option-Left -> moveWordLeft:,
        Option-Right -> moveWordRight:)."""
        option_selectors = {
            "left": "moveWordLeft:",
            "right": "moveWordRight:",
        }
        selector = option_selectors.get(name.lower())
        if selector is None:
            raise ValueError(f"No Option+ mapping for {name!r}")
        delegate = self._ui.window_delegate
        delegate.textView_doCommandBySelector_(self._ui.input_field, selector)
        self.spin(0.05)

    def press_ctrl_tab(self) -> None:
        """Simulate Ctrl+Tab to switch to the next (older) conversation tab."""
        self._send_ctrl_tab(shift=False)

    def press_ctrl_shift_tab(self) -> None:
        """Simulate Ctrl+Shift+Tab to switch to the previous (newer) conversation tab."""
        self._send_ctrl_tab(shift=True)

    def _send_ctrl_tab(self, shift: bool) -> None:
        """Build a synthetic Ctrl+Tab event and deliver it directly to the
        window's performKeyEquivalent_ for test reliability."""
        flags = NSControlKeyMask
        if shift:
            flags |= NSShiftKeyMask
        window = self._ui.quick_window
        win_num = window.windowNumber() if window else 0
        event = NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
            NSKeyDown, (0, 0), flags, 0, win_num, None, "\t", "\t", False, 0x30,
        )
        window.performKeyEquivalent_(event)
        self.spin(0.05)

    def select_text(self, view, start: int, length: int) -> None:
        """Set the selection range on an NSTextView."""
        view.setSelectedRange_((start, length))

    # ------------------------------------------------------------------
    # State reads
    # ------------------------------------------------------------------

    @property
    def input_field(self):
        return self._ui.input_field

    @property
    def text_area(self):
        return self._ui.text_area

    def input_text(self) -> str:
        """Current plain text in the input field."""
        return str(self._ui.input_field.string())

    def conversation_text(self) -> str:
        """Current plain text in the main conversation area."""
        return str(self._ui.text_area.string())

    def clipboard(self) -> str | None:
        """Current pasteboard string."""
        pb = NSPasteboard.generalPasteboard()
        return pb.stringForType_(NSStringPboardType)

    def window_open(self) -> bool:
        """Whether the macLLM panel is currently visible."""
        return self._ui.quick_window is not None

    def autocomplete_visible(self) -> bool:
        """Whether the autocomplete popup is showing."""
        delegate = getattr(self._ui, "window_delegate", None)
        if delegate and hasattr(delegate, "autocomplete") and delegate.autocomplete:
            return delegate.autocomplete.is_visible()
        return False

    def status_title(self) -> str:
        """Current menu bar status text."""
        return str(self._ui.delegate.status_item.title())

    def tab_count(self) -> int:
        """Number of tab views currently rendered in the tab bar."""
        views = getattr(self._ui, "_tab_views", [])
        return len(views)

    def active_tab_title(self) -> str:
        """Title of the currently active conversation."""
        conv = self._ui.macllm.chat_history
        return getattr(conv, "title", "New")

    # ------------------------------------------------------------------
    # Visual capture
    # ------------------------------------------------------------------

    def screenshot(self, path: str) -> bool:
        """Capture the macLLM window to a PNG file."""
        return capture_window_by_title("macLLM", path)

    def check_screenshot(self, path: str, assertion: str,
                         model: str = "gemini/gemini-2.5-flash") -> bool:
        """Send a screenshot to a vision-capable LLM and check an assertion.

        Returns True if the LLM answers YES.  Uses the API key from the
        macLLM runtime config so no extra env vars are needed.
        """
        from litellm import completion
        from macllm.core.config import get_runtime_config

        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        cfg = get_runtime_config()
        kwargs: dict = {"model": model}
        if model.startswith("openai/") or model.startswith("gpt"):
            if cfg.api_keys.openai:
                kwargs["api_key"] = cfg.api_keys.openai
        elif model.startswith("gemini/"):
            if cfg.api_keys.gemini:
                kwargs["api_key"] = cfg.api_keys.gemini

        kwargs["messages"] = [{
            "role": "user",
            "content": [
                {
                    "type": "text",
                    "text": (
                        "Look at this macOS application window screenshot. "
                        f"Answer YES or NO only: {assertion}"
                    ),
                },
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64}"},
                },
            ],
        }]

        response = completion(**kwargs)
        answer = response.choices[0].message.content or ""
        return "yes" in answer.strip().lower()

    # ------------------------------------------------------------------
    # Flow control
    # ------------------------------------------------------------------

    def spin(self, seconds: float = 0.1) -> None:
        """Spin the NSApp run loop so pending events and UI updates process."""
        deadline = NSDate.dateWithTimeIntervalSinceNow_(seconds)
        NSRunLoop.currentRunLoop().runUntilDate_(deadline)

    def wait_for(self, predicate: Callable[[], bool], timeout: float = 5.0,
                 interval: float = 0.1) -> bool:
        """Spin until *predicate* returns True or *timeout* elapses."""
        end = time.time() + timeout
        while time.time() < end:
            self.spin(interval)
            if predicate():
                return True
        return False

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _post_key_event(self, key: str, modifier_mask: int) -> None:
        """Create and post a synthetic NSEvent for *key* with *modifier_mask*."""
        # Resolve key code
        if key in _KEY_CODES:
            code = _KEY_CODES[key]
            chars = ""
        elif key in _CHAR_KEY_CODES:
            code = _CHAR_KEY_CODES[key]
            chars = key
        else:
            raise ValueError(f"No key code for {key!r}")

        window = self._ui.quick_window
        win_num = window.windowNumber() if window else 0

        for event_type in (NSKeyDown, NSKeyUp):
            event = NSEvent.keyEventWithType_location_modifierFlags_timestamp_windowNumber_context_characters_charactersIgnoringModifiers_isARepeat_keyCode_(
                event_type,
                (0, 0),
                modifier_mask,
                0,
                win_num,
                None,
                chars,
                chars,
                False,
                code,
            )
            NSApplication.sharedApplication().postEvent_atStart_(event, True)
