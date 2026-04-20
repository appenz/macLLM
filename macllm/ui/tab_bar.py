"""Tab bar for switching between conversations.

Renders a horizontal strip of Chrome-style tabs between the top bar and
the main text area.  The active tab is white (connecting seamlessly with
the content area below); inactive tabs blend with the window background
and are separated by thin pipe dividers.
"""

from Cocoa import (
    NSBox,
    NSBoxCustom,
    NSNoBorder,
    NSFont,
    NSColor,
    NSMutableParagraphStyle,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSParagraphStyleAttributeName,
    NSAttributedString,
    NSView,
    NSTextField,
)
from AppKit import NSLineBreakByTruncatingTail
import objc


class _ClickableTab(NSView):
    """Tab view that detects clicks and routes to the correct conversation."""

    conv_index = -1
    macllm_ui = None

    def hitTest_(self, point):
        frame = self.frame()
        ox, oy = frame[0]
        w, h = frame[1]
        px, py = float(point[0]), float(point[1])
        if ox <= px <= ox + w and oy <= py <= oy + h:
            local_x = px - ox
            local_y = py - oy
            for sv in self.subviews():
                if isinstance(sv, _CloseButton):
                    sf = sv.frame()
                    sx, sy = sf[0]
                    sw, sh = sf[1]
                    if sx <= local_x <= sx + sw and sy <= local_y <= sy + sh:
                        return sv
            return self
        return None

    def mouseDown_(self, event):
        if self.macllm_ui is not None and self.conv_index >= 0:
            self.macllm_ui.switch_conversation(self.conv_index)


class _CloseButton(NSView):
    """Small x button that removes a conversation."""

    conv_index = -1
    macllm_ui = None

    def mouseDown_(self, event):
        if self.macllm_ui is not None and self.conv_index >= 0:
            self.macllm_ui.close_conversation(self.conv_index)


class TabBarHandler:

    @staticmethod
    def visible_tab_indices(conversation_history, max_tabs=5):
        """Return the list of conversation indices to display as tabs.

        Newest-left ordering: the returned list has higher indices first.
        If the active conversation falls outside the default window,
        center the window on it.
        """
        total = len(conversation_history.conversations)
        if total == 0:
            return []

        active = conversation_history.active_index

        last_n = list(range(max(0, total - max_tabs), total))
        last_n.reverse()

        if active in last_n:
            return last_n

        half = max_tabs // 2
        start = max(0, active - half)
        end = min(total, start + max_tabs)
        start = max(0, end - max_tabs)
        centered = list(range(start, end))
        centered.reverse()
        return centered

    @staticmethod
    def create_or_update_tab_bar(macllm_ui, parent_view, tab_bar_y: int):
        """Create or update the tab bar strip inside *parent_view*."""
        from macllm.ui.core import MacLLMUI

        tab_bar_height = MacLLMUI.tab_bar_height
        tab_bar_width = MacLLMUI.text_area_width

        # --- transparent container (NSView, no clipping) ---
        if not hasattr(macllm_ui, "tab_bar_container"):
            container = NSView.alloc().initWithFrame_(
                ((MacLLMUI.text_area_x, tab_bar_y), (tab_bar_width, tab_bar_height))
            )
            parent_view.addSubview_(container)
            macllm_ui.tab_bar_container = container
        else:
            container = macllm_ui.tab_bar_container
            try:
                if container.superview() is None or container.superview() != parent_view:
                    container.removeFromSuperview()
                    parent_view.addSubview_(container)
            except Exception:
                container = NSView.alloc().initWithFrame_(
                    ((MacLLMUI.text_area_x, tab_bar_y), (tab_bar_width, tab_bar_height))
                )
                parent_view.addSubview_(container)
                macllm_ui.tab_bar_container = container
            container.setFrame_(
                ((MacLLMUI.text_area_x, tab_bar_y), (tab_bar_width, tab_bar_height))
            )

        # --- clear old subviews ---
        if hasattr(macllm_ui, "_tab_views"):
            for tv in macllm_ui._tab_views:
                tv.removeFromSuperview()
        if hasattr(macllm_ui, "_tab_separators"):
            for sep in macllm_ui._tab_separators:
                sep.removeFromSuperview()
        macllm_ui._tab_views = []
        macllm_ui._tab_separators = []

        conv_hist = macllm_ui.macllm.conversation_history
        indices = TabBarHandler.visible_tab_indices(conv_hist)
        if not indices:
            return

        num = len(indices)
        active_idx = conv_hist.active_index

        sep_width = 1
        sep_count = max(0, num - 1)
        usable = tab_bar_width - sep_count * sep_width
        per_tab = max(60, int(usable / num))

        pill_top_pad = 3
        tab_inner_height = tab_bar_height - pill_top_pad
        # The active pill extends below the container so it renders behind
        # the content area's rounded top corners, filling the indent where
        # the two meet.
        overlap = int(MacLLMUI.text_corner_radius) + 4

        close_w = 16
        label_h_pad = 6

        active_bg = MacLLMUI.white
        active_fg = NSColor.blackColor()
        inactive_fg = NSColor.colorWithCalibratedWhite_alpha_(0.35, 1.0)
        close_fg = NSColor.colorWithCalibratedWhite_alpha_(0.55, 1.0)
        close_active_fg = NSColor.colorWithCalibratedWhite_alpha_(0.35, 1.0)
        sep_color = NSColor.colorWithCalibratedWhite_alpha_(0.65, 1.0)

        x = 0

        for i, conv_index in enumerate(indices):
            is_active = (conv_index == active_idx)
            is_last = (i == num - 1)
            conv = conv_hist.conversations[conv_index]

            tab_w = (tab_bar_width - x) if is_last else per_tab

            tab_view = _ClickableTab.alloc().initWithFrame_(
                ((x, 0), (tab_w, tab_inner_height))
            )
            tab_view.conv_index = conv_index
            tab_view.macllm_ui = macllm_ui

            if is_active:
                pill = NSBox.alloc().initWithFrame_(
                    ((0, -overlap), (tab_w, tab_inner_height + overlap))
                )
                pill.setBoxType_(NSBoxCustom)
                pill.setBorderType_(NSNoBorder)
                pill.setCornerRadius_(4.0)
                pill.setFillColor_(active_bg)
                tab_view.addSubview_(pill)

            # Title label with running/approval indicators
            title = conv.title or "New Agent"
            if conv.pending_approval:
                title = "⏸ " + title
            elif conv.is_agent_running():
                title = "⟳ " + title
            para = NSMutableParagraphStyle.alloc().init()
            para.setAlignment_(1)
            para.setLineBreakMode_(NSLineBreakByTruncatingTail)
            attrs = {
                NSFontAttributeName: NSFont.systemFontOfSize_(11.0),
                NSForegroundColorAttributeName: active_fg if is_active else inactive_fg,
                NSParagraphStyleAttributeName: para,
            }
            attr_str = NSAttributedString.alloc().initWithString_attributes_(title, attrs)

            label_w = tab_w - close_w - label_h_pad
            label = NSTextField.alloc().initWithFrame_(
                ((label_h_pad, 0), (label_w, tab_inner_height))
            )
            label.setEditable_(False)
            label.setSelectable_(False)
            label.setBezeled_(False)
            label.setDrawsBackground_(False)
            label.setBordered_(False)
            label.setAttributedStringValue_(attr_str)
            tab_view.addSubview_(label)

            # Close button
            close_btn = _CloseButton.alloc().initWithFrame_(
                ((tab_w - close_w - 2, 0), (close_w, tab_inner_height))
            )
            close_btn.conv_index = conv_index
            close_btn.macllm_ui = macllm_ui

            close_para = NSMutableParagraphStyle.alloc().init()
            close_para.setAlignment_(1)
            close_attrs = {
                NSFontAttributeName: NSFont.systemFontOfSize_(11.0),
                NSForegroundColorAttributeName: close_active_fg if is_active else close_fg,
                NSParagraphStyleAttributeName: close_para,
            }
            close_str = NSAttributedString.alloc().initWithString_attributes_(
                "\u00d7", close_attrs
            )
            close_label = NSTextField.alloc().initWithFrame_(
                ((0, 0), (close_w, tab_inner_height))
            )
            close_label.setEditable_(False)
            close_label.setSelectable_(False)
            close_label.setBezeled_(False)
            close_label.setDrawsBackground_(False)
            close_label.setBordered_(False)
            close_label.setAttributedStringValue_(close_str)
            close_btn.addSubview_(close_label)
            tab_view.addSubview_(close_btn)

            container.addSubview_(tab_view)
            macllm_ui._tab_views.append(tab_view)

            x += tab_w

            # Pipe separator between tabs
            if i < num - 1:
                sep = NSBox.alloc().initWithFrame_(
                    ((x, 2), (sep_width, tab_inner_height - 4))
                )
                sep.setBoxType_(NSBoxCustom)
                sep.setBorderType_(NSNoBorder)
                sep.setFillColor_(sep_color)
                container.addSubview_(sep)
                macllm_ui._tab_separators.append(sep)
                x += sep_width
