"""Delegate for browsing chat history in the main conversation text area.

When *macllm_ui* enters "browsing history" mode, the main text view becomes
first-responder and this delegate intercepts key commands so the user can move
up/down, copy a message or insert it into the input field.
"""
from Cocoa import NSObject, NSApp
import objc


class HistoryBrowseDelegate(NSObject):
    """Minimal delegate that handles keyboard navigation while browsing history."""

    macllm_ui = None  # injected after creation

    # ---------------------------------------------------------------------
    # Link click handler (used for expandable output blocks)
    # ---------------------------------------------------------------------
    def textView_clickedOnLink_atIndex_(self, _view, link, _index):  # noqa: N802
        link_str = str(link)
        if link_str.startswith("macllm://toggle-output/"):
            tool_id = link_str.split("/", 3)[-1]
            try:
                from macllm.macllm import MacLLM
                status_mgr = MacLLM.get_status_manager()
                for entry in status_mgr.tool_calls:
                    if entry.id == tool_id:
                        entry.expanded = not entry.expanded
                        self.macllm_ui.update_window()
                        break
            except Exception:
                pass
            return True
        return False

    # ---------------------------------------------------------------------
    # NSTextView command handler
    # ---------------------------------------------------------------------
    def textView_doCommandBySelector_(self, _view, commandSelector):  # noqa: N802
        # Only intervene when we are in browsing mode – otherwise let normal
        # behaviour continue.
        if not getattr(self.macllm_ui, "browsing_history", False):
            return False

        try:
            if commandSelector in ("moveUp:", "moveDown:"):
                delta = -1 if commandSelector == "moveUp:" else 1
                self._move_history(delta)
                return True

            elif commandSelector == "noop:":
                # Handle Command-C for copy.
                current_event = NSApp().currentEvent()
                if current_event and (current_event.modifierFlags() & (1 << 20)):
                    key = current_event.charactersIgnoringModifiers().lower()
                    if key == "c":
                        self.macllm_ui.copy_current_history_to_clipboard()
                        return True
                return False

            elif commandSelector == "insertNewline:":
                # Return – insert message into input field and exit browsing.
                self.macllm_ui.insert_current_history_into_input()
                return True

            elif commandSelector == "cancelOperation:":
                # ESC – abort browsing.
                self.macllm_ui.exit_history_browsing()
                return True

        except Exception as exc:  # pragma: no cover – delegate should never crash UI
            if hasattr(self.macllm_ui, "macllm"):
                self.macllm_ui.macllm.debug_exception(exc)
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _move_history(self, delta: int):
        """Move selection *delta* steps (-1 up, +1 down)."""
        messages = self.macllm_ui.macllm.chat_history.get_displayable_messages()
        history_len = len(messages)
        # If user tries to move *down* past the newest message, return focus to input.
        if delta > 0 and self.macllm_ui.history_index == history_len - 1:
            self.macllm_ui.exit_history_browsing()
            return

        new_idx = max(0, min(history_len - 1, self.macllm_ui.history_index + delta))
        if new_idx != self.macllm_ui.history_index:
            self.macllm_ui.history_index = new_idx
            self.macllm_ui.highlight_current_history()
