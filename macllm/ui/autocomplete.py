from __future__ import annotations
from typing import List

from Cocoa import NSPanel, NSBorderlessWindowMask, NSColor, NSTableView, NSTableColumn, NSScrollView, NSObject, NSIndexSet
import objc


class TableDataSource(NSObject):
    """NSObject subclass to serve as NSTableView data source."""
    
    def initWithPopup_(self, popup):
        self = objc.super(TableDataSource, self).init()
        self.popup = popup
        return self
    
    def numberOfRowsInTableView_(self, _table):  # noqa: N802
        return len(self.popup._suggestions)
    
    def tableView_objectValueForTableColumn_row_(  # noqa: N802
        self, _table, _column, row
    ):  # pylint: disable=unused-argument
        if 0 <= row < len(self.popup._suggestions):
            return self.popup._suggestions[row]
        return ""


class AutocompletePopup:  # pylint: disable=too-few-public-methods
    """Lightweight popup window that lists tag suggestions."""

    def __init__(self, anchor_view):
        """Create an (initially hidden) borderless panel below *anchor_view*."""
        self._anchor_view = anchor_view
        self._panel = None
        self._table_view = None
        self._suggestions: List[str] = []
        self._data_source = None
        self._create_ui()

    # ------------------------------------------------------------------
    # Public API used by *AutocompleteController*
    # ------------------------------------------------------------------
    def show(self, suggestions: List[str]):
        self._suggestions = suggestions
        if not suggestions:
            self.hide()
            return
        # Update / reload table data
        if hasattr(self._table_view, "reloadData"):
            self._table_view.reloadData()
        # Position the popup below the anchor view
        self._position_popup()
        if self._panel and self._panel.isVisible() is False:
            self._panel.orderFrontRegardless()

    def hide(self):
        if self._panel and self._panel.isVisible():
            self._panel.orderOut_(None)

    def update_selection(self, index: int):
        """Highlight *index* in the list view (no-op when in stub mode)."""
        if hasattr(self._table_view, "selectRowIndexes_byExtendingSelection_"):
            # Create proper NSIndexSet instead of Python set
            index_set = NSIndexSet.indexSetWithIndex_(index)
            self._table_view.selectRowIndexes_byExtendingSelection_(  # type: ignore[attr-defined]
                index_set, False
            )
            self._table_view.scrollRowToVisible_(index)  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _create_ui(self):
        """Create NSPanel + NSTableView UI.  On non-GUI platforms this is a noop."""
        # Size for up to 8 rows, 200px wide – can be tweaked later.
        frame = ((0, 0), (200, 160))
        panel = NSPanel.alloc().initWithContentRect_styleMask_backing_defer_(
            frame, NSBorderlessWindowMask, 2, False  # 2 == buffered backing
        )
        panel.setLevel_(3)  # floating window (same as main quick window)
        panel.setBackgroundColor_(NSColor.whiteColor())
        panel.setHasShadow_(True)

        # Table view inside a scroll view
        table = NSTableView.alloc().initWithFrame_(((0, 0), (200, 160)))
        column = NSTableColumn.alloc().initWithIdentifier_("tag")
        column.setWidth_(200)
        table.addTableColumn_(column)
        table.setHeaderView_(None)
        table.setRowHeight_(20)
        table.setDelegate_(self)
        
        # Create and set data source
        self._data_source = TableDataSource.alloc().initWithPopup_(self)
        table.setDataSource_(self._data_source)

        scroll = NSScrollView.alloc().initWithFrame_(((0, 0), (200, 160)))
        scroll.setDocumentView_(table)
        scroll.setHasVerticalScroller_(True)
        scroll.setAutohidesScrollers_(True)

        panel.setContentView_(scroll)
        panel.orderOut_(None)  # hidden by default

        self._panel = panel
        self._table_view = table

    def _position_popup(self):
        """Position the popup window below the anchor view."""
        if not self._panel or not self._anchor_view:
            return
            
        # Get the anchor view's window and convert coordinates
        anchor_window = self._anchor_view.window()
        if not anchor_window:
            return
            
        # Get the current cursor position in the text view
        from Cocoa import NSRange, NSRect
        
        cursor_range = self._anchor_view.selectedRange()
        
        try:
            # Use the layout manager to get the cursor rectangle
            layout_manager = self._anchor_view.layoutManager()
            text_container = self._anchor_view.textContainer()
            
            # Get the bounding rect for the cursor position
            cursor_rect = layout_manager.boundingRectForGlyphRange_inTextContainer_(
                NSRange(cursor_range.location, 0), text_container
            )
            
            # Convert to view coordinates (add text view's origin)
            text_view_bounds = self._anchor_view.bounds()
            cursor_rect.origin.x += text_view_bounds.origin.x
            cursor_rect.origin.y += text_view_bounds.origin.y
            
            # Convert to window coordinates
            cursor_rect_in_window = self._anchor_view.convertRect_toView_(cursor_rect, None)
            
            # Convert to screen coordinates
            screen_rect = anchor_window.convertRectToScreen_(cursor_rect_in_window)
            
        except Exception:
            # Fallback: use the text view's frame if layout manager fails
            text_view_frame = self._anchor_view.frame()
            text_view_in_window = self._anchor_view.superview().convertRect_toView_(text_view_frame, None)
            screen_rect = anchor_window.convertRectToScreen_(text_view_in_window)
        
        # Position popup below the cursor position
        popup_x = screen_rect.origin.x
        popup_y = screen_rect.origin.y - self._panel.frame().size.height - 5  # 5px gap below cursor
        
        # Ensure popup stays on screen
        screen_frame = anchor_window.screen().frame()
        if popup_x + self._panel.frame().size.width > screen_frame.size.width:
            popup_x = screen_frame.size.width - self._panel.frame().size.width
        if popup_x < 0:
            popup_x = 0
        if popup_y < 0:
            popup_y = screen_rect.origin.y + screen_rect.size.height + 5  # Show above instead
            
        self._panel.setFrameOrigin_((popup_x, popup_y))


class AutocompleteController:  # pylint: disable=too-few-public-methods
    """Filter available *tags* and coordinate popup selection/insertions.

    Besides static prefixes this controller now supports *dynamic* suggestions
    supplied by plugins that implement the optional autocomplete hooks."""

    def __init__(self, plugins: List[object], anchor_view):
        # Store plugin refs
        self._plugins = plugins

        # Collect static tag prefixes for quick filtering (used when plugins do
        # not provide dynamic autocomplete).
        all_tags: list[str] = []
        for plugin in plugins:
            try:
                all_tags.extend(plugin.get_prefixes())
            except Exception:  # pragma: no cover – defensive
                pass

        self._static_tags = sorted(all_tags)

        # Populated each time *update_suggestions* is called:
        # list[tuple[str raw, str display]]
        self._entries: list[tuple[str, str]] = []
        self._selected: int = 0

        self._popup = AutocompletePopup(anchor_view)

    # ------------------------------------------------------------------
    # Public helpers called from the *InputFieldDelegate*
    # ------------------------------------------------------------------
    def update_suggestions(self, fragment: str):
        """Refresh suggestions based on current *fragment*.  This now queries
        plugins that support dynamic autocomplete in addition to simple prefix
        filtering."""
        if not fragment.startswith("@"):
            self._popup.hide()
            return

        entries: list[tuple[str, str]] = []  # raw, display
        seen: set[str] = set()

        # 1. Always add matching *static* tag prefixes first so that built-in
        #    tags and user-defined shortcuts take precedence over file-based
        #    suggestions.
        lower = fragment.lower()
        for tag in self._static_tags:
            if tag.lower().startswith(lower):
                entries.append((tag, tag))
                seen.add(tag)

        # 2. Ask plugins that support dynamic autocomplete *after* static
        #    prefixes so their (potentially longer) suggestion list appears
        #    below the built-in tags.  This is important for the FileTag
        #    plugin so that files never outrank normal tag completions.
        for plugin in self._plugins:
            try:
                if not plugin.supports_autocomplete():
                    continue

                # Decide whether to query this plugin: either the fragment
                # matches one of its declared prefixes *or* the plugin has
                # opted in as a catch-all provider via *match_any_autocomplete()*.
                call_plugin = False
                if getattr(plugin, "match_any_autocomplete", lambda: False)():
                    call_plugin = True
                else:
                    for prefix in plugin.get_prefixes():
                        if fragment.lower().startswith(prefix.lower()):
                            call_plugin = True
                            break

                if not call_plugin:
                    continue

                suggestions = plugin.autocomplete(fragment, 10)
                for s in suggestions:
                    if s in seen:
                        continue  # avoid duplicates
                    entries.append((s, plugin.display_string(s)))
                    seen.add(s)
            except Exception:  # pragma: no cover
                continue

        # Keep only the first 10 entries overall
        entries = entries[:10]

        # Prepare popup
        self._entries = entries
        display_list = [disp for _raw, disp in entries]

        self._selected = 0
        self._popup.show(display_list)
        self._popup.update_selection(self._selected)

    def navigate(self, delta: int):
        if not self._entries:
            return
        self._selected = (self._selected + delta) % len(self._entries)
        self._popup.update_selection(self._selected)

    def current_selection(self):
        """Return a ``(raw, display)`` tuple for the highlighted entry.  *raw*
        is the full tag string that will be inserted into the text buffer,
        *display* is what should be rendered in the pill."""
        if self._entries:
            return self._entries[self._selected]
        return None

    def hide(self):
        self._popup.hide()

    # ------------------------------------------------------------------
    # Introspection helpers
    # ------------------------------------------------------------------
    def is_visible(self) -> bool:
        if hasattr(self._popup, "_panel") and self._popup._panel:  # pylint: disable=protected-access
            return bool(self._popup._panel.isVisible())  # type: ignore[func-returns-value]
        return False 