#
# Simple program that creates a menu bar icon with PyObjC
#

from Foundation import NSThread 


from Cocoa import NSApplication, NSStatusBar, NSMenu, NSMenuItem, NSObject, NSImage, NSApp, NSApplicationActivationPolicyRegular
from Cocoa import NSTimer
from Cocoa import NSPasteboard, NSStringPboardType, NSPasteboardTypePNG, NSPasteboardTypeTIFF

from Cocoa import NSPanel, NSScreen, NSPanel, NSBorderlessWindowMask, NSImageView
from Cocoa import NSBorderlessWindowMask
from Cocoa import NSColor
from Cocoa import NSScrollView, NSTextView
from Cocoa import NSFont
from Cocoa import NSBox, NSBoxCustom, NSNoBorder
from Cocoa import NSFontAttributeName, NSForegroundColorAttributeName, NSParagraphStyleAttributeName, NSBackgroundColorAttributeName
from Cocoa import NSMutableParagraphStyle
from Cocoa import NSGraphicsContext
from Cocoa import NSMutableAttributedString

from macllm.ui.main_text import MainTextHandler
from macllm.ui.top_bar import TopBarHandler
from macllm.ui.tab_bar import TabBarHandler
from macllm.ui.history_browse import HistoryBrowseDelegate
from macllm.ui.input_field import InputFieldHandler

from macllm.markdown.blocks import FONT_SIZE

import os
import sys
import objc

import signal
import traceback
from time import sleep

# Helper for dispatching UI updates from background threads
class _UIUpdater(NSObject):
    target = None
    
    def run_(self, sender):
        if _UIUpdater.target:
            _UIUpdater.target._perform_update_from_callback()

_ui_updater = _UIUpdater.alloc().init()


# Custom panel for the quick entry window. This is neededto enable it to become 
# key window and main window

class QuickWindowPanel(NSPanel):
    macllm_ui = None

    def canBecomeKeyWindow(self):
        return True

    def canBecomeMainWindow(self):
        return True

    def performKeyEquivalent_(self, event):
        flags = event.modifierFlags()

        if event.keyCode() == 0x30:  # Tab key
            if flags & (1 << 18):  # NSControlKeyMask
                if self.macllm_ui and self.macllm_ui.macllm:
                    shift = flags & (1 << 17)  # NSShiftKeyMask
                    delta = 1 if shift else -1
                    self.macllm_ui.cycle_conversation(delta)
                    return True

        # Cmd-Return: abort + optional submit
        if event.keyCode() == 0x24 and (flags & (1 << 20)):  # Return + NSCommandKeyMask
            if self.macllm_ui:
                text = ""
                delegate = getattr(self.macllm_ui, 'window_delegate', None)
                if delegate:
                    text = delegate._plain_text_from_view()
                self.macllm_ui.handle_cmd_return(text)
                return True

        # Ctrl-C: abort running agent (no submit)
        chars = event.charactersIgnoringModifiers()
        if chars and chars.lower() == "c" and (flags & (1 << 18)) and not (flags & (1 << 20)):
            if self.macllm_ui:
                self.macllm_ui.handle_abort()
                return True

        handled = objc.super(QuickWindowPanel, self).performKeyEquivalent_(event)
        if handled:
            return True

        # Borderless panels have no Edit menu, so Cmd+C / Cmd+A never reach
        # the first responder through the normal menu-dispatch path.  Handle
        # them here as a fallback for any NSTextView with a text selection.
        flags = event.modifierFlags()
        if flags & (1 << 20):  # NSCommandKeyMask
            chars = event.charactersIgnoringModifiers()
            if chars:
                key = chars.lower()
                responder = self.firstResponder()
                if key == "c" and hasattr(responder, "selectedRange"):
                    if responder.selectedRange().length > 0:
                        responder.copy_(None)
                        return True
                if key == "a" and hasattr(responder, "selectAll_"):
                    responder.selectAll_(None)
                    return True

        return False

class AppDelegate(NSObject):

    # Actions for various events

    def pb_init(self):
        self.pasteboard = NSPasteboard.generalPasteboard()

    def terminate_(self, sender):
        NSApp().terminate_(self)

    def signalCheck_(self, timer):
        pass

    # Create the menu items under the menu bar icon

    def menu(self):
        menu = NSMenu.alloc().init()
        menu.addItem_(NSMenuItem.separatorItem())
        options_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Options", "options:", "")
        menu.addItem_(options_item)
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "terminate:", "")
        menu.addItem_(quit_item)
        return menu

    def options_(self, sender):
        print("Options clicked!")
    
    def openWindowOnStart_(self, timer):
        self.macllm_ui.update_window()

    def autoSubmitQuery_(self, timer):
        query = self.macllm_ui.pending_query
        self.macllm_ui.pending_query = None
        if query:
            self.macllm_ui.handle_user_input(query)

    def scheduleQuitTimer_(self, sender):
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            2.0, self, 'screenshotAndQuit:', None, False)

    def screenshotAndQuit_(self, timer):
        path = getattr(self.macllm_ui, '_quit_screenshot_path', None)
        if path:
            from macllm.utils.screenshot import capture_window_by_title
            ok = capture_window_by_title("macLLM", path)
            if ok:
                print(f"Screenshot saved to {path}")
            else:
                print(f"Warning: failed to capture window screenshot to {path}")
        NSApp().terminate_(None)

    def setup_status_item(self):
        """Create the menu-bar status item and pasteboard. Safe to call
        from both applicationDidFinishLaunching_ and MacLLMUI.start()."""
        if getattr(self, "_status_item_ready", False):
            return
        self._status_item_ready = True

        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(-1)
        self.status_item.setMenu_(self.menu())
        self.status_item.setTitle_(MacLLMUI.status_ready)
        self.status_item.setHighlightMode_(True)
        self.pasteboard = NSPasteboard.generalPasteboard()

    def applicationDidFinishLaunching_(self, notification):
        try:
            self.setup_status_item()

            # Open window on startup if requested
            if self.macllm_ui.macllm and getattr(self.macllm_ui.macllm.args, 'show_window_on_start', False):
                NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                    0.1, self, 'openWindowOnStart:', None, False)

            # Auto-submit a query if one was provided via --query
            if self.macllm_ui.pending_query:
                NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                    0.5, self, 'autoSubmitQuery:', None, False)

        except Exception as e:
            print(f"Initialization failure: {e}")
            traceback.print_exc()
            NSApp().terminate_(self)




class MacLLMUI:

    # Font
    font_size = FONT_SIZE

    # Layout of the window - updated to match specification
    padding = 4
    top_bar_height = 48  # Updated to match new specification
    tab_bar_height = 24  # Conversation tab strip
    text_area_width = 640   # Width for 80 characters
    input_field_height = 90  # 5 lines visible
    input_field_width = text_area_width
    window_corner_radius = 12.0
    text_corner_radius = 8.0
    text_right_inset = 4.0
    fudge = 1 # no idea why this is needed, but it is

    # Everything below is calculated based on the above
    icon_width = 38  # Fixed icon size for top bar
    window_width = text_area_width + padding*2

    # Top bar positioning and sizing
    top_bar_text_field_width = 180  # Width of the text field in top bar
    icon_x = padding + fudge
    text_area_x = padding + fudge
    input_field_x = padding + fudge

    status_ready = "LLM"

    # Colors
    white = NSColor.whiteColor()
    light_grey = NSColor.colorWithCalibratedWhite_alpha_(0.9, 1.0)
    dark_grey  = NSColor.colorWithCalibratedWhite_alpha_(0.8, 1.0)
    darker_grey  = NSColor.colorWithCalibratedWhite_alpha_(0.6, 1.0)
    text_grey  = NSColor.colorWithCalibratedWhite_alpha_(0.5, 1.0)
    text_grey_subtle  = NSColor.colorWithCalibratedWhite_alpha_(0.65, 1.0)

    def __init__(self):
        self.app = None
        self.delegate = None
        self.macllm = None
        self.pending_query = None
        self.pending_screenshot = None

        self.quick_window = None
        self.debug_window = None
        if getattr(sys, "frozen", None):
            assets_dir = os.path.join(os.environ["RESOURCEPATH"], "assets")
        else:
            assets_dir = os.path.join(
                os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                "assets",
            )
        self.dock_image = NSImage.alloc().initByReferencingFile_(os.path.join(assets_dir, "icon.png"))
        self.logo_image = NSImage.alloc().initByReferencingFile_(os.path.join(assets_dir, "icon-nobg.png"))
        
        # Create a high-quality scaled version of the logo for the top bar
        self._create_scaled_logo()
        
        # Preserve input text between window sessions
        self.saved_input_text = ""

        # Browsing history mode state
        self.browsing_history = False
        self.history_index = 0
        self.conversation_viewport_target = "input"

        # Code block keyboard focus state (-1 = none focused)
        self.focused_code_block = -1

    def _create_scaled_logo(self):
        """Create a high-quality scaled version of the logo for the top bar."""
        if self.logo_image and self.logo_image.size().width > 0:
            # Create a new image with the target size
            target_size = (MacLLMUI.icon_width, MacLLMUI.icon_width)
            scaled_image = NSImage.alloc().initWithSize_(target_size)
            
            # Lock focus on the new image for drawing
            scaled_image.lockFocus()
            
            # Set high-quality interpolation
            NSGraphicsContext.currentContext().setImageInterpolation_(3)  # NSImageInterpolationHigh = 3
            
            # Draw the original image scaled to fit
            original_rect = ((0, 0), self.logo_image.size())
            target_rect = ((0, 0), target_size)
            self.logo_image.drawInRect_fromRect_operation_fraction_(target_rect, original_rect, 1, 1.0)  # NSCompositeSourceOver = 1
            
            # Unlock focus
            scaled_image.unlockFocus()
            
            # Use the scaled version
            self.logo_image = scaled_image

    def _fit_conversation_text_to_scroll_view(
        self,
        scroll_view,
        text_view,
        main_area_height,
        text_corner_radius,
        textbox_x_fudge,
        textbox_y_fudge,
    ):
        """Size the conversation text view to the scroll view's clip width."""
        if hasattr(scroll_view, "tile"):
            scroll_view.tile()

        clip_size = scroll_view.contentView().bounds().size
        clip_width = clip_size.width
        clip_height = clip_size.height
        text_width = max(
            0.0,
            clip_width - textbox_x_fudge - MacLLMUI.text_right_inset,
        )
        text_height = max(
            clip_height,
            main_area_height - 2 * text_corner_radius - textbox_y_fudge,
        )
        text_view.setFrame_(((textbox_x_fudge, textbox_y_fudge), (text_width, text_height)))
        text_view.setHorizontallyResizable_(False)
        text_view.setVerticallyResizable_(True)

        text_container = text_view.textContainer()
        if text_container is not None:
            text_container.setWidthTracksTextView_(True)
            text_container.setLineFragmentPadding_(0.0)

        return clip_width

    @staticmethod
    def handle_interrupt(signal, frame):
        NSApp().terminate_(None)

    def iconStatus(self, color):
        self.delegate.status_item.button().setImage_(color)
        return

    def read_clipboard(self):
        content = self.delegate.pasteboard.stringForType_(NSStringPboardType)
        return content

    def read_clipboard_image(self):
        """Read image data from the pasteboard, returning a PIL Image or None."""
        pb = self.delegate.pasteboard
        for ptype in (NSPasteboardTypePNG, NSPasteboardTypeTIFF):
            data = pb.dataForType_(ptype)
            if data:
                from PIL import Image
                import io
                return Image.open(io.BytesIO(bytes(data)))
        return None

    def write_clipboard(self, content):
        self.delegate.pasteboard.declareTypes_owner_([NSStringPboardType], None)
        self.delegate.pasteboard.setString_forType_(content, NSStringPboardType)

    def read_change_count(self):
        return self.delegate.pasteboard.changeCount()
    
    # This is called when the user presses Return in the pop-up window

    def handle_user_input(self, text):
        if text == "":
            return
        conv = self.macllm.chat_history
        conv.submit(text)
        self.update_window()
        InputFieldHandler.clear_input_field(self.input_field)

    def handle_cmd_return(self, text):
        """Cmd+Return: cancel the running agent (if any) and optionally submit new text."""
        conv = self.macllm.chat_history
        if conv.is_agent_running():
            conv.abort()
            self.exit_history_browsing()
        if text:
            conv.submit(text)
        self.update_window()
        InputFieldHandler.clear_input_field(self.input_field)

    def handle_abort(self):
        """Abort the running agent without submitting any text."""
        conv = self.macllm.chat_history
        if conv.is_agent_running():
            conv.abort()
            self.exit_history_browsing()
        self.update_window()

    def set_status_indicator(self, working: bool):
        """No-op — status indicator removed in favour of static label."""
        pass

    def schedule_quit(self, screenshot_path: str | None = None):
        """Schedule optional screenshot + app termination after the query finishes.

        Waits 2 seconds for the UI to render, then captures the window
        (if *screenshot_path* is set) and terminates. Safe to call from
        any thread.
        """
        self._quit_screenshot_path = screenshot_path
        self.delegate.performSelectorOnMainThread_withObject_waitUntilDone_(
            'scheduleQuitTimer:', None, False)

    def request_update(self):
        if not getattr(self, 'quick_window', None) and not getattr(self, 'debug_window', None):
            return
        if NSThread.isMainThread():
            self._perform_update_from_callback()
        else:
            _UIUpdater.target = self
            _ui_updater.performSelectorOnMainThread_withObject_waitUntilDone_('run:', None, False)

    def _perform_update_from_callback(self):
        if getattr(self, 'quick_window', None):
            self.update_window()
        else:
            self.refresh_debug_window()

    def update_window(self):

        # Find the width and height of the screen
        screen_width = NSScreen.mainScreen().frame().size.width
        screen_height = NSScreen.mainScreen().frame().size.height
        
        # Calculate minimum text height using the new handler
        minimum_text_height = MainTextHandler.calculate_minimum_text_height(self.macllm)
        
        # Calculate window dimensions according to specification
        # 90% of screen height, width for 80 characters
        max_window_height = int(screen_height * 0.9)
        window_width = MacLLMUI.window_width

        # --- PADDING & CORNERS ---
        padding = MacLLMUI.padding
        window_corner_radius = MacLLMUI.window_corner_radius
        text_corner_radius = MacLLMUI.text_corner_radius

        # --- HEIGHTS ---
        padding_internal_fudge = 5 # no idea why this is needed, but it is
        textbox_x_fudge = 3
        textbox_y_fudge = 3
        top_bar_height = MacLLMUI.top_bar_height
        tab_bar_height = MacLLMUI.tab_bar_height
        entry_height = MacLLMUI.input_field_height
        # 4 paddings: top, top-bar/tab-bar, main/entry, bottom
        # (tab bar sits directly on top of main area with no gap)
        total_padding = padding * 4

        conv_has_messages = bool(MainTextHandler.displayable_messages(self.macllm.chat_history))

        if conv_has_messages:
            # Calculate optimal main area height based on minimum text height
            text_container_padding = text_corner_radius * 2
            optimal_main_area_height = minimum_text_height + text_container_padding

            total_ui_height = top_bar_height + tab_bar_height + optimal_main_area_height + entry_height + total_padding + padding_internal_fudge
            window_height = min(total_ui_height, max_window_height)
            main_area_height = window_height - (top_bar_height + tab_bar_height + entry_height + total_padding + padding_internal_fudge)
        else:
            # Tab bar sits flush on top of the input field when empty
            main_area_height = 0
            window_height = top_bar_height + tab_bar_height + entry_height + padding * 3

        # --- Y COORDINATES ---
        # Y=0 is at the bottom
        input_field_y = padding
        if conv_has_messages:
            main_area_y = input_field_y + entry_height + padding + padding_internal_fudge
            tab_bar_y = main_area_y + main_area_height
        else:
            main_area_y = 0  # unused when hidden
            tab_bar_y = input_field_y + entry_height
        top_bar_y = tab_bar_y + tab_bar_height + padding

        if self.quick_window is None:
            new_window = True
            win = QuickWindowPanel.alloc()
            win.macllm_ui = self
            self.quick_window = win

            # Position window in center of screen
            frame = ( 
                      ( (screen_width - window_width) / 2-window_corner_radius, 
                         (screen_height - window_height) / 2-window_corner_radius
                      ), (window_width+2*window_corner_radius, window_height+2*window_corner_radius) 
                    ) 
            window_mask = NSBorderlessWindowMask
            win.initWithContentRect_styleMask_backing_defer_(frame, window_mask, 2, 0)
            win.setTitle_("🦙 macLLM")
            win.setLevel_(3)  # floating window

            # Set the background color of the window to be transparent
            win.setBackgroundColor_(NSColor.clearColor())
        else:
            new_window = False
            win = self.quick_window
            # Update window frame for resize
            frame = ( 
                      ( (screen_width - window_width) / 2-window_corner_radius, 
                         (screen_height - window_height) / 2-window_corner_radius
                      ), (window_width+2*window_corner_radius, window_height+2*window_corner_radius) 
                    ) 
            win.setFrame_display_(frame, True)
        
        if new_window:
            # Create an NSBox to serve as the rounded, colored background
            box = NSBox.alloc().initWithFrame_(((0, 0), (window_width+window_corner_radius, window_height+window_corner_radius)))
            box.setBoxType_(NSBoxCustom) 
            box.setBorderType_(NSNoBorder)  
            box.setCornerRadius_(window_corner_radius)
            #box.setTransparent_(True)
            box.setFillColor_(MacLLMUI.light_grey)
            win.contentView().addSubview_(box)
            self.background_box = box
        else:
            # Update existing background box frame
            box = self.background_box
            box.setFrame_(((0, 0), (window_width+window_corner_radius, window_height+window_corner_radius)))

        # ----- Top bar with dark grey container, icon, context area, and text field -----
        TopBarHandler.create_or_update_top_bar(self, box, top_bar_y)

        # ----- Tab bar for conversation switching -----
        TabBarHandler.create_or_update_tab_bar(self, box, tab_bar_y)

        # ----- Main conversation area (middle section) as a scrollable NSTextView with rounded corners -------------------

        if new_window:
            text_container = NSBox.alloc().initWithFrame_(
                ((MacLLMUI.text_area_x, main_area_y),
                 (MacLLMUI.text_area_width, main_area_height))
            )
            text_container.setBoxType_(NSBoxCustom)
            text_container.setBorderType_(NSNoBorder)
            text_container.setCornerRadius_(text_corner_radius)
            text_container.setFillColor_(MacLLMUI.white)
            box.addSubview_(text_container)
            self.text_container = text_container
        else:
            text_container = self.text_container
            # Update existing text container and scroll view frames
            text_container.setFrame_(((MacLLMUI.text_area_x, main_area_y),
                                     (MacLLMUI.text_area_width, main_area_height)))
            # The active tab pill extends below the tab bar into the text
            # area region. Re-add text_container so it stays on top in the
            # sibling z-order and covers the pill overflow.
            text_container.removeFromSuperview()
            box.addSubview_(text_container)

        text_container.setHidden_(not conv_has_messages)

        if new_window:
            scroll_view = NSScrollView.alloc().initWithFrame_(
                ((0, 3),
                (MacLLMUI.text_area_width - 2*text_corner_radius, main_area_height - 2*text_corner_radius))
            )

            scroll_view.setHasVerticalScroller_(True)
            scroll_view.setHasHorizontalScroller_(False)
            scroll_view.setAutohidesScrollers_(False)
            scroll_view.setScrollerStyle_(0)  # NSScrollerStyleLegacy
            scroller = scroll_view.verticalScroller()
            if scroller:
                scroller.setHidden_(False)
            self.scroll_view = scroll_view

            text_view = NSTextView.alloc().initWithFrame_(((textbox_x_fudge, textbox_y_fudge), (MacLLMUI.text_area_width - 2*text_corner_radius, main_area_height - 2*text_corner_radius)))
            text_view.setEditable_(False)
            text_view.setDrawsBackground_(False)  # Let the container handle the background
            text_view.setFont_(NSFont.systemFontOfSize_(MacLLMUI.font_size))
            self.text_area = text_view

            # Attach delegate for history browsing
            history_delegate = HistoryBrowseDelegate.alloc().init()
            history_delegate.macllm_ui = self
            text_view.setDelegate_(history_delegate)
            self.history_delegate = history_delegate

            # Attach text view to the scroll view and add to container
            scroll_view.setDocumentView_(text_view)
            text_container.addSubview_(scroll_view)
        else:
            # Reuse existing scroll and text views
            scroll_view = self.scroll_view
            text_view = self.text_area

            # Update frames to match new size
            scroll_view.setFrame_(((0, 3),
                (MacLLMUI.text_area_width - 2*text_corner_radius, main_area_height - 2*text_corner_radius)))
            text_view.setFrame_(((textbox_x_fudge, textbox_y_fudge), (MacLLMUI.text_area_width - 2*text_corner_radius, main_area_height - 2*text_corner_radius)))

            # Ensure scroll view is in the container hierarchy (in case it was removed)
            if scroll_view.superview() is None:
                text_container.addSubview_(scroll_view)

        # Render content and show scrollbar when content significantly exceeds visible area
        scroll_threshold = 20  # Buffer to avoid scrollbar for minor overflows
        rendered_height = MainTextHandler.set_text_content(self.macllm, text_view)
        visible_height = scroll_view.contentView().bounds().size.height
        need_scroll = rendered_height > (visible_height + scroll_threshold)
        scroll_view.setHasVerticalScroller_(need_scroll)
        self._fit_conversation_text_to_scroll_view(
            scroll_view,
            text_view,
            main_area_height,
            text_corner_radius,
            textbox_x_fudge,
            textbox_y_fudge,
        )
        if need_scroll:
            # Text reflows once the scrollbar consumes clip width.
            MainTextHandler.set_text_content(self.macllm, text_view)

        self.render_conversation_viewport()

        # Update the top bar text with model and token information
        self.update_top_bar_text()
        self.refresh_debug_window()

        # ----- Input field at bottom with rounded corners ---------------------------------------------------------------

        if new_window:
            # Create input field using the new handler
            (input_container, input_field, delegate) = InputFieldHandler.create_input_field(
                box, (0, input_field_y), self, self.saved_input_text)
            self.input_container = input_container
            self.input_field = input_field
            self.window_delegate = delegate
            
            # Clear saved text after restoring it
            self.saved_input_text = ""

            # --------------------------------------------------------------
            # Provide list of available @tag prefixes for autocomplete.
            # --------------------------------------------------------------
            try:
                available_tags = []
                if hasattr(self.macllm, "plugins"):
                    for plugin in self.macllm.plugins:
                        available_tags.extend(plugin.get_prefixes())
                if hasattr(delegate, "autocomplete") and delegate.autocomplete:
                    delegate.autocomplete.update_suggestions("")  # seed list
            except Exception as exc:  # pragma: no cover
                self.macllm.debug_exception(exc)
        else:
            # Update existing input field position
            InputFieldHandler.update_input_field_position(
                self.input_container, self.input_field, (0, input_field_y), self)
            # Re-add input container so it stays above the tab bar's active
            # pill overflow in the sibling z-order.
            self.input_container.removeFromSuperview()
            box.addSubview_(self.input_container)

        if new_window:
            # Move the window to the front and activate it
            win.display()
            win.orderFrontRegardless()
            win.makeKeyWindow()  # Make it the key window
            self.app.activateIgnoringOtherApps_(True)
            InputFieldHandler.focus_input_field(self.input_field)  # Set focus to the input field
        else:
            # Just refresh the window display for resize
            win.needsDisplay = True
            win.display()
            # Restore first-responder after removeFromSuperview/re-add
            # cycles that macOS silently resigned.
            if self.browsing_history and hasattr(self, 'text_area'):
                win.makeFirstResponder_(self.text_area)
            elif hasattr(self, 'input_field'):
                InputFieldHandler.focus_input_field(self.input_field)

    def update_top_bar_text(self):
        if not hasattr(self, "top_bar_text_view"):
            return

        from macllm.core.llm_service import get_model_for_speed
        conv = self.macllm.chat_history
        speed = getattr(conv, 'speed_level', 'normal') or 'normal'
        model = get_model_for_speed(speed)
        input_tokens = conv.usage.input_tokens
        output_tokens = conv.usage.output_tokens

        # Determine agent and speed for display
        agent_cls = getattr(self.macllm.chat_history, "agent_cls", None)
        agent_display = agent_cls.macllm_name.capitalize() if agent_cls else "Default"

        speed = getattr(self.macllm.chat_history, "speed_level", "normal") or "normal"
        speed_display = {
            "fast": "Fast",
            "normal": "Normal",
            "slow": "Think",
        }.get(speed.lower(), "Normal")

        line1 = f"{agent_display} / {speed_display}"
        line2 = f"{model}"
        line3 = f"{input_tokens} in / {output_tokens} out"
        txt = f"{line1}\n{line2}\n{line3}"

        para = NSMutableParagraphStyle.alloc().init()
        para.setAlignment_(2)                          # right

        attrs_provider_name = {
            NSFontAttributeName: NSFont.systemFontOfSize_(11),
            NSForegroundColorAttributeName: MacLLMUI.text_grey,
            NSParagraphStyleAttributeName: para,
        }

        attrs_rest_of_text = {
            NSFontAttributeName: NSFont.systemFontOfSize_(11),
            NSForegroundColorAttributeName: MacLLMUI.text_grey_subtle,
            NSParagraphStyleAttributeName: para,
        }

        # Create attributed string with mixed styles
        attr_str = NSMutableAttributedString.alloc().initWithString_(txt)
        
        # Apply provider style to the first line (Mode)
        first_line_len = len(line1)
        attr_str.addAttributes_range_(attrs_provider_name, (0, first_line_len))
        
        # Apply rest of text style to everything after the first line
        rest_range = (first_line_len, len(txt) - first_line_len)
        attr_str.addAttributes_range_(attrs_rest_of_text, rest_range)
        
        self.top_bar_text_view.textStorage().setAttributedString_(attr_str)

    # ------------------------------------------------------------------
    # History browsing helpers
    # ------------------------------------------------------------------
    def begin_history_browsing(self):
        """Enter history browsing mode (focus main text, highlight latest)."""
        if self.browsing_history:
            return
        self.browsing_history = True
        self.conversation_viewport_target = "history"
        messages = MainTextHandler.displayable_messages(self.macllm.chat_history)
        self.history_index = max(0, len(messages) - 1)
        # Focus main area and highlight
        if hasattr(self, "text_area"):
            self.text_area.window().makeFirstResponder_(self.text_area)
        self.render_conversation_viewport()

    def _history_range_is_visible(self, text_range):
        """Return True when any part of *text_range* is already visible."""
        try:
            layout_manager = self.text_area.layoutManager()
            text_container = self.text_area.textContainer()
            if not layout_manager or not text_container:
                return False
            glyph_range = layout_manager.glyphRangeForCharacterRange_actualCharacterRange_(text_range, None)
            rect = layout_manager.boundingRectForGlyphRange_inTextContainer_(glyph_range, text_container)
            origin = self.text_area.textContainerOrigin()
            rect.origin.x += origin.x
            rect.origin.y += origin.y
            visible = self.text_area.visibleRect()
            rect_top = rect.origin.y + rect.size.height
            visible_top = visible.origin.y + visible.size.height
            return rect_top >= visible.origin.y and rect.origin.y <= visible_top
        except Exception:
            return False

    def _remove_history_highlight(self):
        highlight_range = MainTextHandler._last_highlight_range
        if not highlight_range or not hasattr(self, "text_area"):
            MainTextHandler._last_highlight_range = None
            return
        text_storage = self.text_area.textStorage()
        text_length = text_storage.length()
        if highlight_range[0] + highlight_range[1] <= text_length:
            text_storage.removeAttribute_range_(NSBackgroundColorAttributeName, highlight_range)
        MainTextHandler._last_highlight_range = None

    def _scroll_conversation_to_bottom(self):
        if not hasattr(self, "text_area"):
            return
        self.text_area.scrollRangeToVisible_((self.text_area.textStorage().length(), 0))

    def activate_input_viewport(self):
        """Make the input field the active conversation viewport target."""
        self.browsing_history = False
        self.focused_code_block = -1
        self.conversation_viewport_target = "input"
        self.render_conversation_viewport()

    def render_conversation_viewport(self):
        """Render highlight and scroll from the active viewport target."""
        if not hasattr(self, "text_area"):
            return

        if self.conversation_viewport_target != "history":
            self._remove_history_highlight()
            self._scroll_conversation_to_bottom()
            return

        message_ranges = MainTextHandler._message_ranges
        if not (0 <= self.history_index < len(message_ranges)):
            self._remove_history_highlight()
            return

        text_storage = self.text_area.textStorage()
        text_length = text_storage.length()
        previous_range = MainTextHandler._last_highlight_range
        if previous_range and previous_range[0] + previous_range[1] <= text_length:
            text_storage.removeAttribute_range_(NSBackgroundColorAttributeName, previous_range)

        start, length = message_ranges[self.history_index]
        if start + length > text_length:
            MainTextHandler.set_text_content(self.macllm, self.text_area, highlight_index=self.history_index)
            return

        highlight_color = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.9, 0.9, 1.0, 1.0)
        highlight_range = (start, length)
        text_storage.addAttributes_range_(
            {NSBackgroundColorAttributeName: highlight_color},
            highlight_range,
        )
        MainTextHandler._last_highlight_range = highlight_range
        if not self._history_range_is_visible(highlight_range):
            self.text_area.scrollRangeToVisible_((start, max(1, length)))

    def highlight_current_history(self):
        """Move the history highlight without disturbing the current scroll."""
        self.conversation_viewport_target = "history"
        self.render_conversation_viewport()

    def copy_current_history_to_clipboard(self):
        """Copy the selected history entry (raw text only) to the clipboard."""
        try:
            messages = MainTextHandler.displayable_messages(self.macllm.chat_history)
            message = messages[self.history_index]
            text = message['content']
            self.write_clipboard(text)
        except IndexError:
            pass

    def insert_current_history_into_input(self):
        """Paste selected history entry into the input field and exit browsing."""
        try:
            messages = MainTextHandler.displayable_messages(self.macllm.chat_history)
            message = messages[self.history_index]
            entry_text = message['content']
            if hasattr(self, "input_field") and self.input_field:
                InputFieldHandler.clear_input_field(self.input_field)
                self.input_field.insertText_(entry_text)
        except IndexError:
            pass
        self.exit_history_browsing()
        # Focus back to input field for editing
        if hasattr(self, "input_field"):
            InputFieldHandler.focus_input_field(self.input_field)

    def exit_history_browsing(self):
        """Return to normal mode (remove highlight & focus input)."""
        if not self.browsing_history:
            return
        self.activate_input_viewport()
        # Focus back to input field
        if hasattr(self, "input_field"):
            InputFieldHandler.focus_input_field(self.input_field)

    # ------------------------------------------------------------------
    # Code block keyboard navigation
    # ------------------------------------------------------------------
    def begin_code_block_focus(self):
        """Enter code block focus mode (focuses text area, highlights first block)."""
        from macllm.markdown import get_code_block_count
        if get_code_block_count() == 0:
            return False
        if not self.browsing_history:
            self.browsing_history = True
            if hasattr(self, "text_area"):
                self.text_area.window().makeFirstResponder_(self.text_area)
        self.focused_code_block = 0
        self._apply_code_block_highlight()
        return True

    def cycle_code_block(self, delta):
        """Move focus to the next (+1) or previous (-1) code block."""
        from macllm.markdown import get_code_block_count
        count = get_code_block_count()
        if count == 0:
            return
        if self.focused_code_block < 0:
            self.focused_code_block = 0 if delta > 0 else count - 1
        else:
            self.focused_code_block = (self.focused_code_block + delta) % count
        self._apply_code_block_highlight()

    def copy_focused_code_block(self):
        """Copy the currently focused code block to the clipboard."""
        if self.focused_code_block < 0:
            return False
        from macllm.markdown import get_code_block_ranges, get_code_block_content
        ranges = get_code_block_ranges()
        if self.focused_code_block >= len(ranges):
            return False
        block_id = ranges[self.focused_code_block][0]
        content = get_code_block_content(block_id)
        if content:
            self.write_clipboard(content)
            return True
        return False

    def exit_code_block_focus(self):
        """Leave code block focus and return to input."""
        self.focused_code_block = -1
        self.exit_history_browsing()

    def _apply_code_block_highlight(self):
        """Re-render and apply a background highlight to the focused code block."""
        from macllm.markdown import get_code_block_ranges
        from Cocoa import NSColor, NSBackgroundColorAttributeName
        if not hasattr(self, "text_area"):
            return
        MainTextHandler.set_text_content(self.macllm, self.text_area)
        ranges = get_code_block_ranges()
        if 0 <= self.focused_code_block < len(ranges):
            _, start, length = ranges[self.focused_code_block]
            ts = self.text_area.textStorage()
            if start + length <= ts.length():
                highlight = NSColor.colorWithCalibratedRed_green_blue_alpha_(
                    0.85, 0.90, 1.0, 1.0)
                ts.addAttributes_range_(
                    {NSBackgroundColorAttributeName: highlight},
                    (start, length),
                )
            self.text_area.scrollRangeToVisible_((start, length))

    # ------------------------------------------------------------------
    # Conversation tab switching
    # ------------------------------------------------------------------
    def _save_input_to_conversation(self):
        """Persist the current input field text onto the active conversation."""
        if hasattr(self, 'window_delegate') and self.window_delegate and hasattr(self, 'input_field'):
            try:
                text = self.window_delegate._plain_text_from_view(strip_ends=False)
            except Exception:
                text = self.input_field.string() if hasattr(self.input_field, 'string') else ""
            self.macllm.chat_history.saved_input_text = text

    def _restore_input_from_conversation(self):
        """Restore the input field text from the now-active conversation."""
        if hasattr(self, 'input_field'):
            text = self.macllm.chat_history.saved_input_text or ""
            self.input_field.setString_(text)
            if text and hasattr(self, 'window_delegate'):
                try:
                    self.window_delegate._rebuild_buffer_with_pills()
                except Exception:
                    pass

    def switch_conversation(self, index):
        """Switch to the conversation at *index* and refresh the UI."""
        self._save_input_to_conversation()
        self.macllm.switch_to_conversation(index)
        if hasattr(self, "input_field"):
            InputFieldHandler.clear_input_field(self.input_field)
        self.update_window()
        self._restore_input_from_conversation()
        if hasattr(self, "input_field"):
            InputFieldHandler.focus_input_field(self.input_field)

    def cycle_conversation(self, delta):
        """Cycle conversations while preserving per-tab draft input."""
        self._save_input_to_conversation()
        old_index = self.macllm.conversation_history.active_index
        self.macllm.cycle_conversation(delta)
        new_index = self.macllm.conversation_history.active_index
        if new_index != old_index and hasattr(self, "input_field"):
            InputFieldHandler.clear_input_field(self.input_field)
        self._restore_input_from_conversation()
        if hasattr(self, "input_field"):
            InputFieldHandler.focus_input_field(self.input_field)

    def new_conversation(self):
        """Create a conversation while preserving the current tab's draft."""
        self._save_input_to_conversation()
        self.macllm.new_conversation()
        if hasattr(self, "input_field"):
            InputFieldHandler.clear_input_field(self.input_field)
        self.update_window()
        if hasattr(self, "input_field"):
            InputFieldHandler.focus_input_field(self.input_field)

    def close_conversation(self, index):
        """Delete the conversation at *index* and refresh the UI."""
        conv = None
        try:
            conv = self.macllm.conversation_history.conversations[index]
        except Exception:
            pass
        if conv is not None and self.debug_window is not None:
            self.debug_window.close_for_conversation(getattr(conv, "conv_id", None))
        self.macllm.delete_conversation(index)
        if hasattr(self, "input_field"):
            InputFieldHandler.clear_input_field(self.input_field)
        self.update_window()
        if hasattr(self, "input_field"):
            InputFieldHandler.focus_input_field(self.input_field)

    def open_debug_window(self):
        """Open a passive debug log window for the active conversation."""
        from macllm.ui.debug_window import DebugWindow

        if self.debug_window is None:
            self.debug_window = DebugWindow(self)
        self.debug_window.open(self.macllm.chat_history)

    def refresh_debug_window(self):
        if self.debug_window is not None:
            self.debug_window.refresh()

    # ------------------------------------------------------------------
    # Existing methods
    # ------------------------------------------------------------------
    def close_window(self):
        # Save current input text before closing
        if hasattr(self, 'input_field') and self.input_field:
            # Prefer extracting plain text (expanding tag attachments) so that
            # tags/shortcuts survive across window close/open cycles.
            try:
                if hasattr(self, 'window_delegate') and self.window_delegate:
                    # Preserve whitespace as-typed; rebuilding will re-tokenize
                    self.saved_input_text = self.window_delegate._plain_text_from_view(strip_ends=False)
                else:
                    self.saved_input_text = self.input_field.string()
            except Exception:
                # Fallback in case delegate extraction fails
                self.saved_input_text = self.input_field.string()
        
        # Ensure we leave browsing mode cleanly
        self.browsing_history = False

        self.quick_window.orderOut_(None)
        self.quick_window = None
        if self.debug_window is not None:
            self.debug_window.close()
            self.debug_window = None
        # Deactivate our app to return focus to the previous application
        self.app.hide_(None)
    
    # Handle the hotkey press
    def hotkey_pressed(self):
        if self.quick_window is None:
            self.update_window()
        else:
            self.close_window()

    def _install_main_menu(self):
        """Build a minimal main menu bar so Cmd+Q works in the app bundle."""
        main_menu = NSMenu.alloc().init()

        app_menu_item = NSMenuItem.alloc().init()
        main_menu.addItem_(app_menu_item)

        app_menu = NSMenu.alloc().init()
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(
            "Quit macLLM", "terminate:", "q"
        )
        app_menu.addItem_(quit_item)
        app_menu_item.setSubmenu_(app_menu)

        self.app.setMainMenu_(main_menu)

    def start(self, dont_run_app: bool = False):
        # Pointer to main class, we need this for callback
        signal.signal(signal.SIGINT, self.handle_interrupt)

        self.app = NSApplication.sharedApplication()
        self.delegate = AppDelegate.alloc().init()
        self.delegate.macllm_ui = self
        self.app.setDelegate_(self.delegate)
        self.app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        self._install_main_menu()
        self.delegate.setup_status_item()

        self.delegate.pb_init()
        
        # Change the App icon
        # Only set the icon if the image is valid (has non-zero size)
        if self.dock_image.size().width > 0 and self.dock_image.size().height > 0:
            self.app.setApplicationIconImage_(self.dock_image)

        # Recurring timer gives CPython a chance to dispatch pending
        # signals (SIGINT) while the Cocoa run loop owns the main thread.
        NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self.delegate, 'signalCheck:', None, True)

        # Start the application event loop (unless in test mode)
        if not dont_run_app:
            self.app.run()

