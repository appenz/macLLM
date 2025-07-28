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
    NSColor,
    NSBezierPath,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSAttributedString,
    NSMakeRect,
    NSImage,
    NSMutableAttributedString,
    NSAttachmentAttributeName,
)
from macllm.ui.autocomplete import AutocompleteController
import objc

# ---------------------------------------------------------------------------
# Custom NSTextAttachment subclass that applies a vertical offset so the
# bottom of the attachment aligns with the text baseline without altering the
# line height.  We override *attachmentBoundsForTextContainer:* to adjust the
# returned rect by the desired offset (negative values move it downward).
# ---------------------------------------------------------------------------


class _InlineTextAttachment(objc.lookUpClass("NSTextAttachment")):
    """NSTextAttachment that stores a vertical offset (in points)."""

    _verticalOffset = 0.0  # default – no shift

    # Setters / getters -----------------------------------------------------
    def setVerticalOffset_(self, value):  # noqa: N802 – Objective-C naming
        self._verticalOffset = value

    def verticalOffset(self):  # noqa: D401
        """Return stored vertical offset (for completeness)."""
        return self._verticalOffset

    # Cocoa callback --------------------------------------------------------
    def attachmentBoundsForTextContainer_proposedLineFragment_glyphPosition_characterIndex_(
        self, textContainer, lineFrag, position, charIndex
    ):  # noqa: N802
        rect = objc.super(_InlineTextAttachment, self).attachmentBoundsForTextContainer_proposedLineFragment_glyphPosition_characterIndex_(
            textContainer, lineFrag, position, charIndex
        )
        rect.origin.y = self._verticalOffset
        return rect

# ---------------------------------------------------------------------------
# Custom attachment cell that draws a rounded-rect “pill” with the tag text
# ---------------------------------------------------------------------------


def _make_tag_attachment(tag: str) -> NSAttributedString:
    font = NSFont.systemFontOfSize_(13.0)

    attrs = {NSFontAttributeName: font, NSForegroundColorAttributeName: NSColor.blackColor()}
    text_ns = objc.lookUpClass("NSString").stringWithString_(tag)
    txt_size = text_ns.sizeWithAttributes_(attrs)

    # Horizontal / vertical padding around the text so that the pill isn't
    # clipped and looks visually centred on the baseline.
    padding_x = 6  # left / right padding
    padding_y = 1  # top / bottom padding

    width = txt_size.width + 2 * padding_x
    height = txt_size.height

    img = NSImage.alloc().initWithSize_((width, height))
    img.lockFocus()

    # Background pill - very light blue
    NSColor.colorWithCalibratedRed_green_blue_alpha_(0.8, 0.9, 1.0, 1.0).set()
    path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(0, 0, width, height), 4.0, 4.0
    )
    path.fill()

    # Draw text in the middle of the pill
    text_rect = NSMakeRect(
        padding_x,
        (height - txt_size.height) / 2,
        txt_size.width,
        txt_size.height,
    )
    text_ns.drawInRect_withAttributes_(text_rect, attrs)

    img.unlockFocus()

    # Use our custom attachment class so we can apply a vertical offset that
    # keeps the pill’s bottom flush with the baseline while preserving normal
    # line height.
    attachment = _InlineTextAttachment.alloc().init()
    attachment.setImage_(img)

    # Build mutable attributed string around the attachment
    attr_string = NSMutableAttributedString.alloc().initWithAttributedString_(
        NSAttributedString.attributedStringWithAttachment_(attachment)
    )

    # Lower the pill by the font's descender (negative) *and* the extra bottom
    # padding we added.  This ensures the bottom edge sits exactly on the
    # baseline.
    vertical_offset = font.descender() - padding_y
    attachment.setVerticalOffset_(vertical_offset)

    # Create attributed string and adjust baseline so the pill doesn't push the
    # line height up.  We lower the attachment by half of the extra height to
    # centre it vertically relative to the text baseline.
    # No need for NSBaselineOffset adjustments now – the attachment’s own
    # bounds provide the correct alignment without increasing line height.

    return attr_string


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
        return self

    # ------------------------------------------------------------------
    # Cocoa delegate callbacks
    # ------------------------------------------------------------------
    def textDidChange_(self, _notification): 
        """Refresh autocomplete list whenever the text changes."""
        try:
            fragment = self._current_fragment()
            if self.autocomplete:
                self.autocomplete.update_suggestions(fragment)
        except Exception as exc:  # pragma: no cover
            self.macllm_ui.macllm.debug_exception(exc)

    # NSTextView keyboard command handler
    def textView_doCommandBySelector_(self, _view, commandSelector):
        try:
            if self.autocomplete and self.autocomplete.is_visible():
                # --- Tag editing mode, the autocomplete popup is visible ---------
                if commandSelector in ('insertNewline:', 'insertTab:'):
                    # Accept autocomplete selection
                    selection = self.autocomplete.current_selection()
                    if selection:
                        self._insert_tag(selection)
                        self.autocomplete.hide()
                    return True
                elif commandSelector in ('moveUp:', 'moveDown:'):
                    # Navigate popup
                    delta = -1 if commandSelector == 'moveUp:' else 1
                    self.autocomplete.navigate(delta)
                    return True
                elif commandSelector == 'cancelOperation:':
                    # Hide popup (ESC)
                    self.autocomplete.hide()
                    return True
                elif commandSelector == 'noop:':  # Block Cmd+C/V/N in tag mode
                    return True
                # Allow normal text editing (backspace, delete, arrows, etc.)
                return False
                
            else:
                # --- Normal mode, the autocomplete popup is not visible ---------
                if commandSelector in ('insertNewline:'):
                    # Send message
                    input_text = self._plain_text_from_view()
                    self.macllm_ui.handle_user_input(input_text)
                    return True
                elif commandSelector == 'cancelOperation:':
                    # Close window (ESC)
                    self.macllm_ui.close_window()
                    return True
                elif commandSelector == 'noop:':  # Handle Command-C/V/N
                    current_event = NSApp().currentEvent()
                    if current_event and (current_event.modifierFlags() & (1 << 20)):
                        key = current_event.charactersIgnoringModifiers().lower()
                        if key == 'c':
                            self.macllm_ui.write_clipboard(self.text_view.string())
                            self.macllm_ui.close_window()
                            return True
                        if key == 'v':
                            clipboard_content = self.macllm_ui.read_clipboard()
                            if clipboard_content:
                                self.text_view.setString_(clipboard_content)
                            return True
                        if key == 'n':
                            self.macllm_ui.macllm.chat_history.reset()
                            self.macllm_ui.update_window()
                            return True
                # Allow default behavior for other keys in normal mode
                return False
                
        except Exception as exc:  # pragma: no cover
            self.macllm_ui.macllm.debug_exception(exc)
            return False

    # ------------------------------------------------------------------
    # Helper functions
    # ------------------------------------------------------------------
    def _current_fragment(self) -> str:
        """Return the word fragment before the caret (used for filtering)."""
        cursor = self.text_view.selectedRange().location  # type: ignore[attr-defined]
        full_text = self.text_view.string()
        start = cursor
        while start > 0 and full_text[start - 1] not in (' ', '\n', '\t'):
            start -= 1
        return full_text[start:cursor]

    def _insert_tag(self, tag):  # type: ignore[override]
        """Insert an auto-completed tag.  *tag* can be either a string or a
        tuple ``(raw, display)`` where *raw* is the full underlying tag text
        (e.g. ``@"/long/path.txt"``) and *display* is the short label shown in
        the UI pill (e.g. ``path.txt``)."""

        if isinstance(tag, tuple):
            raw_tag, display_text = tag
        else:
            raw_tag = display_text = tag

        # Build pill image using the *display* text
        attr = _make_tag_attachment(display_text)

        # Get typing attributes, but clean them first. If we just inserted a
        # tag, the typing attributes will contain the previous tag's raw
        # value, which we don't want to carry over.
        TAG_ATTR_NAME = "macLLMTagString"
        typing_attrs = self.text_view.typingAttributes().mutableCopy()
        if typing_attrs.objectForKey_(TAG_ATTR_NAME):
            typing_attrs.removeObjectForKey_(TAG_ATTR_NAME)

        # Now, create the full attributed string for the tag.
        # Start with a mutable copy of the visual attachment.
        mutable_attr = attr.mutableCopy()

        # Add the cleaned typing attributes.
        mutable_attr.addAttributes_range_(typing_attrs, NSRange(0, 1))

        # Finally, set the raw tag value, ensuring it overwrites anything
        # that might have slipped through.
        mutable_attr.addAttribute_value_range_(TAG_ATTR_NAME, raw_tag, NSRange(0, 1))

        attr = mutable_attr

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
    def _plain_text_from_view(self) -> str:
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
                TAG_ATTR_NAME = "macLLMTagString"

                tag_text = attrs.get(TAG_ATTR_NAME)

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

        return "".join(result).strip()


class InputFieldHandler:
    """Handler class for creating and managing input field components."""
    
    @staticmethod
    def create_input_field(parent_view, position, macllm_ui):
        """
        Create input field container and text field.
        
        Args:
            parent_view: The parent view to add the input field to
            position: (x, y) position for the input field
            macllm_ui: Reference to the main UI class (contains constants)
            
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

        # --------------------------------------------------------------
        # Delegate & autocomplete setup
        # --------------------------------------------------------------
        delegate = InputFieldDelegate.alloc().initWithTextView_(input_field)
        delegate.macllm_ui = macllm_ui

        # Create autocomplete controller with the full plugin list so that
        # dynamic suggestions (e.g. from the new file-plugin) are supported.
        plugin_list = macllm_ui.macllm.plugins if hasattr(macllm_ui.macllm, "plugins") else []
        delegate.autocomplete = AutocompleteController(plugin_list, input_field)

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