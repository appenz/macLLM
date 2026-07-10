from Cocoa import (
    NSBox,
    NSBoxCustom,
    NSNoBorder,
    NSImageView,
    NSTextView,
    NSView,
    NSTextField,
    NSFont,
    NSColor,
    NSMutableParagraphStyle,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSParagraphStyleAttributeName,
    NSAttributedString,
)
from AppKit import NSLineBreakByClipping
from pathlib import Path
from urllib.parse import urlparse

_SOURCE_ICONS = {
    "file": "📁",
    "note": "📝",
    "web": "🌐",
    "clipboard": "📋",
}


def _source_label(source: dict) -> str:
    """Derive a short display label from a source identity dict."""
    kind = source.get("kind", "")
    ref = source.get("ref", "") or ""
    if kind == "clipboard":
        return "clipboard"
    if kind in ("file", "note"):
        return Path(ref).name or ref
    if kind == "web":
        parsed = urlparse(ref)
        host = (parsed.hostname or parsed.netloc or "").lower()
        path = parsed.path.rstrip("/") or ""
        if path and path != "/":
            label = f"{host}{path}"
        else:
            label = host or ref
        return label
    return ref or kind


def _source_open_target(source: dict) -> tuple[str | None, str | None]:
    """Return ``(url, path)`` for click handling from a source identity dict."""
    kind = source.get("kind", "")
    ref = source.get("ref", "") or ""
    if kind == "web":
        return ref, None
    if kind in ("file", "note"):
        return None, ref
    return None, None


class _DebugButton(NSView):
    macllm_ui = None

    def hitTest_(self, point):
        frame = self.frame()
        ox, oy = frame[0]
        w, h = frame[1]
        px, py = float(point[0]), float(point[1])
        if (ox <= px <= ox + w and oy <= py <= oy + h) or (0 <= px <= w and 0 <= py <= h):
            return self
        return None

    def mouseDown_(self, event):
        if self.macllm_ui is not None:
            self.macllm_ui.open_debug_window()


class _SourceLine(NSView):
    """Clickable source line. Clipboard sources are not clickable."""

    source_entry = None

    def hitTest_(self, point):
        entry = self.source_entry
        if entry is None or entry.get("kind") == "clipboard":
            return None
        url, path = _source_open_target(entry)
        if not url and not path:
            return None
        frame = self.frame()
        ox, oy = frame[0]
        w, h = frame[1]
        px, py = float(point[0]), float(point[1])
        if (ox <= px <= ox + w and oy <= py <= oy + h) or (0 <= px <= w and 0 <= py <= h):
            return self
        return None

    def mouseDown_(self, event):
        entry = self.source_entry
        if entry is None:
            return
        url, path = _source_open_target(entry)
        try:
            from AppKit import NSWorkspace
            from Foundation import NSURL

            workspace = NSWorkspace.sharedWorkspace()
            if url:
                workspace.openURL_(NSURL.URLWithString_(url))
            elif path:
                workspace.openFile_(path)
        except Exception:
            pass


# Main Handler for the top bar that renders the logo, Sources and statistics
class TopBarHandler:

    @staticmethod
    def render_source_items(macllm_ui, parent_view, origin_x: int, origin_y: int, height: int, available_width: int):
        """Render the first six Sources, filling each three-line column top-to-bottom."""
        if hasattr(macllm_ui, "source_lines"):
            for line in macllm_ui.source_lines:
                line.removeFromSuperview()

        source_lines = []
        try:
            conversation = getattr(macllm_ui.macllm, "chat_history", None)
            sources = list(getattr(conversation, "sources", [])) if conversation else []
            sources = sources[:6]
            if not sources:
                macllm_ui.source_lines = []
                return

            columns = 2
            rows = 3
            column_gap = 8
            column_width = max(0, (available_width - column_gap * (columns - 1)) / columns)
            line_height = height / rows

            for index, entry in enumerate(sources):
                column, row = divmod(index, rows)
                x = origin_x + column * (column_width + column_gap)
                y = origin_y + height - (row + 1) * line_height
                line = TopBarHandler.render_source_line(
                    macllm_ui=macllm_ui,
                    parent_view=parent_view,
                    x=x,
                    y=y,
                    width=column_width,
                    height=line_height,
                    source=entry,
                )
                source_lines.append(line)
        except Exception:
            source_lines = []

        macllm_ui.source_lines = source_lines

    @staticmethod
    def render_source_line(macllm_ui, parent_view, x: int, y: int, width: int, height: int, source):
        """Render one source as regular text with no background."""
        line = _SourceLine.alloc().initWithFrame_(((x, y), (width, height)))
        line.source_entry = source
        parent_view.addSubview_(line)

        kind = source.get("kind", "")
        icon = _SOURCE_ICONS.get(kind, "")
        label = _source_label(source)
        text = f"{icon} {label}".strip()
        if text:
            text_view = NSTextView.alloc().initWithFrame_(((0, 0), (width, height)))
            text_view.setEditable_(False)
            text_view.setSelectable_(False)
            text_view.setDrawsBackground_(False)
            text_view.setTextContainerInset_((0.0, 0.0))
            text_view.setHorizontallyResizable_(False)
            text_view.setVerticallyResizable_(False)
            if text_view.textContainer() is not None:
                text_view.textContainer().setContainerSize_((width * 8, height))
                text_view.textContainer().setWidthTracksTextView_(False)
                text_view.textContainer().setHeightTracksTextView_(False)
                text_view.textContainer().setLineFragmentPadding_(0.0)

            paragraph_style = NSMutableParagraphStyle.alloc().init()
            paragraph_style.setLineBreakMode_(NSLineBreakByClipping)
            attrs = {
                NSFontAttributeName: NSFont.systemFontOfSize_(11.0),
                NSForegroundColorAttributeName: NSColor.blackColor(),
                NSParagraphStyleAttributeName: paragraph_style,
            }
            attr_str = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
            text_view.textStorage().setAttributedString_(attr_str)
            text_view.setClipsToBounds_(True)
            line.addSubview_(text_view)

        return line

    @staticmethod
    def create_or_update_top_bar(macllm_ui, parent_view, top_bar_y: int):
        text_corner_radius = macllm_ui.text_corner_radius
        # Create/update container
        if not hasattr(macllm_ui, "top_bar_container"):
            top_bar_container = NSBox.alloc().initWithFrame_(
                ((macllm_ui.text_area_x, top_bar_y), (macllm_ui.text_area_width, macllm_ui.top_bar_height))
            )
            top_bar_container.setBoxType_(NSBoxCustom)
            top_bar_container.setBorderType_(NSNoBorder)
            top_bar_container.setCornerRadius_(text_corner_radius)
            top_bar_container.setFillColor_(macllm_ui.dark_grey)
            parent_view.addSubview_(top_bar_container)
            macllm_ui.top_bar_container = top_bar_container
        else:
            top_bar_container = macllm_ui.top_bar_container
            # If the container is not attached to the current parent_view, reattach it
            try:
                if top_bar_container.superview() is None or top_bar_container.superview() != parent_view:
                    top_bar_container.removeFromSuperview()
                    parent_view.addSubview_(top_bar_container)
            except Exception:
                # If anything goes wrong, recreate the container from scratch
                top_bar_container = NSBox.alloc().initWithFrame_(
                    ((macllm_ui.text_area_x, top_bar_y), (macllm_ui.text_area_width, macllm_ui.top_bar_height))
                )
                top_bar_container.setBoxType_(NSBoxCustom)
                top_bar_container.setBorderType_(NSNoBorder)
                top_bar_container.setCornerRadius_(text_corner_radius)
                top_bar_container.setFillColor_(macllm_ui.dark_grey)
                parent_view.addSubview_(top_bar_container)
                macllm_ui.top_bar_container = top_bar_container
            top_bar_container.setFrame_(((macllm_ui.text_area_x, top_bar_y), (macllm_ui.text_area_width, macllm_ui.top_bar_height)))

        # Layout within top bar
        top_bar_internal_padding = 8
        icon_x_internal = 0
        # Align elements consistently with previous layout
        icon_y = int((macllm_ui.top_bar_height - macllm_ui.icon_width) / 2) - 5
        text_y = icon_y
        text_height = macllm_ui.top_bar_height - text_y - 10

        debug_button_size = 24
        debug_button_gap = 4
        context_area_x = icon_x_internal + macllm_ui.icon_width + top_bar_internal_padding
        debug_button_x = macllm_ui.text_area_width - debug_button_size - top_bar_internal_padding
        text_field_x = debug_button_x - debug_button_gap - macllm_ui.top_bar_text_field_width
        context_available_width = max(0, text_field_x - context_area_x)

        # Logo image view
        if not hasattr(macllm_ui, "logo_image_view"):
            image_view = NSImageView.alloc().initWithFrame_(((icon_x_internal, icon_y), (macllm_ui.icon_width, macllm_ui.icon_width)))
            image_view.setImage_(macllm_ui.logo_image)
            image_view.setImageScaling_(3)
            image_view.setImageAlignment_(1)
            image_view.setImageFrameStyle_(0)
            image_view.setAnimates_(False)
            image_view.setContentHuggingPriority_forOrientation_(1000, 0)
            image_view.setContentHuggingPriority_forOrientation_(1000, 1)
            top_bar_container.addSubview_(image_view)
            macllm_ui.logo_image_view = image_view
        else:
            image_view = macllm_ui.logo_image_view
            # Ensure the image view is attached to the current container
            if image_view.superview() is None or image_view.superview() != top_bar_container:
                image_view.removeFromSuperview()
                top_bar_container.addSubview_(image_view)
            image_view.setFrame_(((icon_x_internal, icon_y), (macllm_ui.icon_width, macllm_ui.icon_width)))

        # Right-aligned multi-line text view
        if not hasattr(macllm_ui, "top_bar_text_view"):
            top_bar_text_view = NSTextView.alloc().initWithFrame_(((text_field_x, text_y), (macllm_ui.top_bar_text_field_width, text_height)))
            top_bar_text_view.setString_("")
            top_bar_text_view.setDrawsBackground_(False)
            top_bar_text_view.setEditable_(False)
            top_bar_text_view.setSelectable_(False)
            top_bar_text_view.setTextContainerInset_((0.0, 0.0))

            paragraph_style = NSMutableParagraphStyle.alloc().init()
            paragraph_style.setAlignment_(2)  # right
            text_attributes = {
                NSFontAttributeName: NSFont.systemFontOfSize_(11.0),
                NSForegroundColorAttributeName: macllm_ui.text_grey_subtle,
                NSParagraphStyleAttributeName: paragraph_style,
            }
            top_bar_text_view.setTypingAttributes_(text_attributes)
            top_bar_container.addSubview_(top_bar_text_view)
            macllm_ui.top_bar_text_view = top_bar_text_view
        else:
            top_bar_text_view = macllm_ui.top_bar_text_view
            # Ensure the text view is attached to the current container
            if top_bar_text_view.superview() is None or top_bar_text_view.superview() != top_bar_container:
                top_bar_text_view.removeFromSuperview()
                top_bar_container.addSubview_(top_bar_text_view)
            top_bar_text_view.setFrame_(((text_field_x, text_y), (macllm_ui.top_bar_text_field_width, text_height)))
            top_bar_text_view.setTextContainerInset_((0.0, 0.0))

        # Debug log button to the right of the mode/model/token status text.
        if not hasattr(macllm_ui, "debug_button_view"):
            debug_button = _DebugButton.alloc().initWithFrame_(
                ((debug_button_x, text_y), (debug_button_size, text_height))
            )
            debug_button.macllm_ui = macllm_ui
            label = NSTextField.alloc().initWithFrame_(((0, 0), (debug_button_size, text_height)))
            label.setEditable_(False)
            label.setSelectable_(False)
            label.setBezeled_(False)
            label.setDrawsBackground_(False)
            label.setBordered_(False)
            para = NSMutableParagraphStyle.alloc().init()
            para.setAlignment_(1)
            attrs = {
                NSFontAttributeName: NSFont.systemFontOfSize_(14.0),
                NSForegroundColorAttributeName: macllm_ui.text_grey,
                NSParagraphStyleAttributeName: para,
            }
            label.setAttributedStringValue_(
                NSAttributedString.alloc().initWithString_attributes_("🐞", attrs)
            )
            debug_button.addSubview_(label)
            top_bar_container.addSubview_(debug_button)
            macllm_ui.debug_button_view = debug_button
            macllm_ui.debug_button_label = label
        else:
            debug_button = macllm_ui.debug_button_view
            if debug_button.superview() is None or debug_button.superview() != top_bar_container:
                debug_button.removeFromSuperview()
                top_bar_container.addSubview_(debug_button)
            debug_button.macllm_ui = macllm_ui
            debug_button.setFrame_(((debug_button_x, text_y), (debug_button_size, text_height)))
            if hasattr(macllm_ui, "debug_button_label"):
                macllm_ui.debug_button_label.setFrame_(((0, 0), (debug_button_size, text_height)))
            # Keep the click target above the non-editable status text in z-order.
            debug_button.removeFromSuperview()
            top_bar_container.addSubview_(debug_button)

        # Render Sources as a three-column text grid.
        TopBarHandler.render_source_items(
            macllm_ui=macllm_ui,
            parent_view=top_bar_container,
            origin_x=context_area_x,
            origin_y=text_y,
            height=text_height,
            available_width=context_available_width,
        )
