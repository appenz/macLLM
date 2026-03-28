#
# Input field handler for macLLM UI
#

from Cocoa import (
    NSObject,
    NSTextView,
    NSScrollView,
    NSBox,
    NSBoxCustom,
    NSNoBorder,
    NSFont,
    NSApp,
    NSRange,
)
from macllm.ui.autocomplete import AutocompleteController
from macllm.ui.tag_render import (
    TAG_ATTR_NAME,
    build_tag_attributed,
    find_token_range,
    display_string_for_tag,
    build_input_attributed_with_caret,
)
from macllm.core.skills import SkillsRegistry
from macllm.core.llm_service import get_model_for_speed
import objc

TAG_ATTR_NAME_CONST = TAG_ATTR_NAME


class InputFieldDelegate(NSObject):
    """Delegate class for handling NSTextView events, shortcuts, and autocomplete."""

    macllm_ui = None  # Will be injected by *InputFieldHandler*

    # ------------------------------------------------------------------
    # Initialisation helpers
    # ------------------------------------------------------------------
    def initWithTextView_(self, text_view):
        self = objc.super(InputFieldDelegate, self).init()
        self.text_view = text_view
        self.text_view.setDelegate_(self)
        self.autocomplete = None  # type: AutocompleteController | None
        self._rebuilding = False  # suppress re-entrant textDidChange during rebuilds
        return self

    # ------------------------------------------------------------------
    # Cocoa delegate callbacks
    # ------------------------------------------------------------------
    def textDidChange_(self, _notification): 
        """Refresh autocomplete list whenever the text changes."""
        try:
            if getattr(self, "_rebuilding", False):
                return
            # IME guard: skip while composing marked text
            if hasattr(self.text_view, 'hasMarkedText') and self.text_view.hasMarkedText():
                return
            fragment = self._current_fragment()
            if self.autocomplete:
                self.autocomplete.update_suggestions(fragment)
            # Full-buffer re-render with pill conversion
            self._rebuild_buffer_with_pills()
        except Exception as exc:  # pragma: no cover
            self.macllm_ui.macllm.debug_exception(exc)

    # Intercept character input for pending approval prompts
    def textView_shouldChangeTextInRange_replacementString_(self, _view, _range, string):
        try:
            if string and len(string) == 1:
                from macllm.macllm import MacLLM
                from macllm.ui.approval import ApprovalRenderer
                status_mgr = MacLLM.get_status_manager()
                if ApprovalRenderer.handle_key(string, status_mgr):
                    return False
        except Exception:
            pass
        return True

    # NSTextView keyboard command handler
    def textView_doCommandBySelector_(self, _view, commandSelector):
        try:
            # --- Cmd-key shortcuts work regardless of autocomplete state ---
            if commandSelector == 'noop:':
                current_event = NSApp().currentEvent()
                if current_event and (current_event.modifierFlags() & (1 << 20)):
                    key = current_event.charactersIgnoringModifiers().lower()
                    if key in ('1', '2', '3'):
                        if key == '1':
                            new_speed = 'fast'
                        elif key == '2':
                            new_speed = 'normal'
                        else:
                            new_speed = 'slow'
                        self.macllm_ui.macllm.chat_history.speed_level = new_speed
                        self.macllm_ui.macllm.llm_metadata['model'] = get_model_for_speed(new_speed)
                        self.macllm_ui.update_top_bar_text()
                        return True
                    if key == 'c':
                        self.text_view.copy_(None)
                        return True
                    if key == 'v':
                        if hasattr(self.text_view, 'pasteAndMatchStyle_'):
                            self.text_view.pasteAndMatchStyle_(None)
                        else:
                            clipboard_content = self.macllm_ui.read_clipboard()
                            if clipboard_content:
                                self.text_view.insertText_(clipboard_content)
                        return True
                    if key == 'n':
                        self.macllm_ui.macllm.chat_history.reset(clear_persisted=True)
                        self.macllm_ui.update_window()
                        return True
                return False

            if self.autocomplete and self.autocomplete.is_visible():
                # --- Tag editing mode, the autocomplete popup is visible ---------
                if commandSelector == 'insertNewline:':
                    selection = self.autocomplete.current_selection()
                    if selection:
                        self._insert_tag(selection)
                        try:
                            self.text_view.insertText_(" ")
                        except Exception:
                            pass
                        self.autocomplete.hide()
                    return True
                elif commandSelector == 'insertTab:':
                    selection = self.autocomplete.current_selection()
                    if selection:
                        raw_tag = selection[0] if isinstance(selection, tuple) else selection
                        if raw_tag.endswith('"') and (raw_tag.startswith('@"') or raw_tag.startswith('/"')):
                            raw_edit = raw_tag[:-1]
                        else:
                            raw_edit = raw_tag
                        rng = self.text_view.selectedRange()
                        fragment = self._current_fragment()
                        replace_start = rng.location - len(fragment)
                        self.text_view.textStorage().replaceCharactersInRange_withString_(
                            NSRange(replace_start, len(fragment)), raw_edit
                        )
                        self.text_view.setSelectedRange_(NSRange(replace_start + len(raw_edit), 0))
                        self.autocomplete.update_suggestions(raw_edit)
                    return True
                elif commandSelector in ('moveUp:', 'moveDown:'):
                    delta = -1 if commandSelector == 'moveUp:' else 1
                    self.autocomplete.navigate(delta)
                    return True
                elif commandSelector == 'cancelOperation:':
                    self.autocomplete.hide()
                    return True
                return False
                
            else:
                # --- Normal mode, the autocomplete popup is not visible ---------
                if commandSelector == 'moveUp:':
                    if self._caret_on_first_line():
                        self.macllm_ui.begin_history_browsing()
                        return True
                    return False
                elif commandSelector == 'insertTab:':
                    if self.macllm_ui.begin_code_block_focus():
                        return True
                    return False
                elif commandSelector in ('insertNewline:'):
                    current_event = NSApp().currentEvent()
                    shift_pressed = current_event and (current_event.modifierFlags() & (1 << 17))
                    if shift_pressed:
                        self.text_view.insertText_("\n")
                        return True
                    input_text = self._plain_text_from_view()
                    self.macllm_ui.handle_user_input(input_text)
                    return True
                elif commandSelector == 'cancelOperation:':
                    self.macllm_ui.close_window()
                    return True
                return False
                
        except Exception as exc:  # pragma: no cover
            self.macllm_ui.macllm.debug_exception(exc)
            return False

    # ------------------------------------------------------------------
    # Helper functions
    # ------------------------------------------------------------------
    def _current_fragment(self) -> str:
        """Return the tag fragment before the caret, respecting quotes/escapes."""
        cursor = self.text_view.selectedRange().location  # type: ignore[attr-defined]
        full_text: str = self.text_view.string()

        # Guard against transient states where the caret can momentarily be
        # beyond the end of the string (or negative). Clamp to valid range.
        if cursor > len(full_text):
            cursor = len(full_text)
        elif cursor < 0:
            cursor = 0

        # Walk left until we hit whitespace *outside* quotes.
        start = cursor
        in_quotes = False
        while start > 0:
            ch = full_text[start - 1]
            if ch == '"':
                # Check if this is an opening quote for a tag (preceded by @ or /)
                # If so, include the tag prefix and stop - don't toggle in_quotes
                # which would incorrectly extend past whitespace before the tag.
                if start >= 2 and full_text[start - 2] in ('@', '/'):
                    start -= 2  # include both @ (or /) and the opening quote
                    break
                in_quotes = not in_quotes
                start -= 1
                continue
            if ch in (' ', '\n', '\t') and not in_quotes:
                break
            start -= 1
        return full_text[start:cursor]

    def _caret_on_first_line(self) -> bool:
        """Return True if the caret is currently on the very first line of the text view."""
        rng = self.text_view.selectedRange()
        if rng.location == 0:
            return True
        text_before = self.text_view.string()[: rng.location]
        return '\n' not in text_before

    def _insert_tag(self, tag):  # type: ignore[override]
        """Insert an auto-completed tag.  *tag* can be either a string or a
        tuple ``(raw, display)`` where *raw* is the full underlying tag text
        (e.g. ``@"/long/path.txt"``) and *display* is the short label shown in
        the UI pill (e.g. ``path.txt``)."""

        if isinstance(tag, tuple):
            raw_tag, display_text = tag
        else:
            raw_tag = display_text = tag

        # Build attributed pill using shared renderer with cleaned typing attrs
        typing_attrs = self.text_view.typingAttributes().mutableCopy()
        if typing_attrs.objectForKey_(TAG_ATTR_NAME_CONST):
            typing_attrs.removeObjectForKey_(TAG_ATTR_NAME_CONST)
        attr = build_tag_attributed(raw_tag, display_text, typing_attrs)

        # Replace the current word fragment with the attachment
        rng = self.text_view.selectedRange()  # current caret range
        fragment = self._current_fragment()
        replace_start = rng.location - len(fragment)

        self.text_view.textStorage().replaceCharactersInRange_withAttributedString_(  # type: ignore[attr-defined]
            NSRange(replace_start, len(fragment)), attr
        )

        # Move caret to position immediately after the attachment (1 char)
        self.text_view.setSelectedRange_(NSRange(replace_start + 1, 0))  # type: ignore[attr-defined]


    # ------------------------------------------------------------------
    # Plain-text extraction helpers
    # ------------------------------------------------------------------
    def _plain_text_from_view(self, strip_ends: bool = True) -> str:
        """Return the text view contents as a plain string, converting tag
        attachments back to their underlying tag text.  Spaces are inserted
        before/after a tag when needed so that words are delimited properly.
        """

        text_storage = self.text_view.textStorage()  # type: ignore[attr-defined]
        raw_str = text_storage.string()

        result: list[str] = []

        # Iterate through the characters, replacing object-replacement chars
        # (U+FFFC) with their associated tagString representation.
        for idx, ch in enumerate(raw_str):
            if ch == "\ufffc":  # Attachment placeholder
                # Retrieve the attachment at this character position
                attrs, _ = text_storage.attributesAtIndex_effectiveRange_(idx, None)
                tag_text = attrs.get(TAG_ATTR_NAME_CONST)

                if tag_text is None:
                    # Unknown attachment – treat as empty string
                    continue

                # Insert leading space if previous char isn't whitespace
                if result and not result[-1].endswith((" ", "\n", "\t")):
                    result.append(" ")

                result.append(str(tag_text))

                # Look ahead to decide if we need a trailing space
                if idx + 1 < len(raw_str):
                    next_char = raw_str[idx + 1]
                    if next_char not in (" ", "\n", "\t"):
                        result.append(" ")
            else:
                result.append(ch)

        joined = "".join(result)
        return joined.strip() if strip_ends else joined

    # ------------------------------------------------------------------
    # Full-buffer rebuild helpers
    # ------------------------------------------------------------------
    def _rebuild_buffer_with_pills(self) -> None:
        """Rebuild full buffer from plain text with pills and keep caret."""
        tv = self.text_view
        # Get plain text by expanding attachments
        plain = self._plain_text_from_view(strip_ends=False)
        # Compute caret plain index by scanning up to current selection
        rng = tv.selectedRange()
        raw_storage = tv.textStorage()
        raw_str = raw_storage.string()
        caret_plain = 0
        for idx, ch in enumerate(raw_str[: rng.location]):
            if ch == "\ufffc":
                attrs, _ = raw_storage.attributesAtIndex_effectiveRange_(idx, None)
                tag_text = attrs.get(TAG_ATTR_NAME_CONST)
                caret_plain += len(tag_text) if tag_text else 0
            else:
                caret_plain += 1

        typing_attrs = tv.typingAttributes()
        plugins = getattr(self.macllm_ui.macllm, 'plugins', [])
        shortcuts_list = SkillsRegistry.list_manual_commands()

        attr_str, caret_attr = build_input_attributed_with_caret(
            plain, typing_attrs, shortcuts_list, plugins, caret_plain
        )

        # Apply replacement in one batch
        ts = tv.textStorage()
        self._rebuilding = True
        ts.beginEditing()
        try:
            ts.setAttributedString_(attr_str)
        finally:
            ts.endEditing()
            self._rebuilding = False
        tv.setSelectedRange_(NSRange(caret_attr, 0))


class InputFieldHandler:
    """Handler class for creating and managing input field components."""
    
    @staticmethod
    def create_input_field(parent_view, position, macllm_ui, initial_text=""):
        """
        Create input field container and text field.
        
        Args:
            parent_view: The parent view to add the input field to
            position: (x, y) position for the input field
            macllm_ui: Reference to the main UI class (contains constants)
            initial_text: Optional initial text to set in the input field
            
        Returns:
            tuple: (input_container, input_field, delegate)
        """
        textbox_x_fudge = 3
        textbox_y_fudge = 3
        text_corner_radius = macllm_ui.text_corner_radius
        
        # Create a container view with rounded corners for the input field
        input_container = NSBox.alloc().initWithFrame_(
            ((macllm_ui.input_field_x, position[1]), 
             (macllm_ui.input_field_width, macllm_ui.input_field_height))
        )
        input_container.setBoxType_(NSBoxCustom)
        input_container.setBorderType_(NSNoBorder)
        input_container.setCornerRadius_(text_corner_radius)
        input_container.setFillColor_(macllm_ui.white)
        parent_view.addSubview_(input_container)

        # ------------------------------------------------------------------
        # Create NSTextView (multi-line) inside a small scroll view so text can
        # wrap and we can apply attributed strings (highlighted tags).
        # ------------------------------------------------------------------
        scroll_view = NSScrollView.alloc().initWithFrame_(
            ((textbox_x_fudge, textbox_y_fudge),
             (macllm_ui.input_field_width - 2 * text_corner_radius,
              macllm_ui.input_field_height - 2 * text_corner_radius))
        )
        scroll_view.setHasVerticalScroller_(False)
        scroll_view.setHasHorizontalScroller_(False)
        scroll_view.setAutohidesScrollers_(True)

        input_field = NSTextView.alloc().initWithFrame_(((0, 0), scroll_view.frame().size))
        input_field.setFont_(NSFont.systemFontOfSize_(13.0))
        input_field.setDrawsBackground_(False)
        input_field.setAutomaticQuoteSubstitutionEnabled_(False)
        input_field.setAutomaticDashSubstitutionEnabled_(False)

        scroll_view.setDocumentView_(input_field)
        input_container.addSubview_(scroll_view)

        # Set initial text if provided
        if initial_text:
            input_field.setString_(initial_text)
            # Place caret at end so rebuild maps correctly
            try:
                input_field.setSelectedRange_(NSRange(len(initial_text), 0))
            except Exception:
                pass

        # --------------------------------------------------------------
        # Delegate & autocomplete setup
        # --------------------------------------------------------------
        delegate = InputFieldDelegate.alloc().initWithTextView_(input_field)
        delegate.macllm_ui = macllm_ui

        # One-time conversion of restored plain text into pills
        try:
            if initial_text:
                delegate._rebuild_buffer_with_pills()
        except Exception:
            pass

        # Create autocomplete controller with the full plugin list so that
        # dynamic suggestions (e.g. from the new file-plugin) are supported.
        plugin_list = macllm_ui.macllm.plugins if hasattr(macllm_ui.macllm, "plugins") else []
        # Provide configured slash skills to autocomplete (list of triggers like '/blog').
        shortcuts_list = SkillsRegistry.list_manual_commands()
        delegate.autocomplete = AutocompleteController(plugin_list, input_field, shortcuts=shortcuts_list)

        return (input_container, input_field, delegate)

    @staticmethod
    def update_input_field_position(input_container, input_field, position, macllm_ui):
        """
        Update the position and size of existing input field components.
        
        Args:
            input_container: The input container NSBox
            input_field: The input field NSTextField
            position: (x, y) position for the input field
            macllm_ui: Reference to the main UI class (contains constants)
        """
        textbox_x_fudge = 3
        textbox_y_fudge = 3
        text_corner_radius = macllm_ui.text_corner_radius
        
        # Update existing input container and field frames
        input_container.setFrame_(((macllm_ui.input_field_x, position[1]), 
                                  (macllm_ui.input_field_width, macllm_ui.input_field_height)))
        
        # Adjust frame of the internal scroll view + text view
        if isinstance(input_field.superview(), NSScrollView):
            scroll_view = input_field.superview()
            scroll_view.setFrame_(((textbox_x_fudge, textbox_y_fudge),
                                   (macllm_ui.input_field_width - 2 * text_corner_radius,
                                    macllm_ui.input_field_height - 2 * text_corner_radius)))
            input_field.setFrame_(((0, 0), scroll_view.frame().size))

    @staticmethod
    def focus_input_field(input_field):
        """Set focus to the input field."""
        if hasattr(input_field, 'window') and input_field.window():
            input_field.window().makeFirstResponder_(input_field)

    @staticmethod
    def clear_input_field(input_field):
        """Clear the text content of the input field."""
        if hasattr(input_field, 'setString_'):
            input_field.setString_("")
        else:
            input_field.setString_("")  # NSTextView 
            input_field.setString_("")  # NSTextView 