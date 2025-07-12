#
# Simple program that creates a menu bar icon with PyObjC
#

from Foundation import NSThread 


from Cocoa import NSApplication, NSStatusBar, NSMenu, NSMenuItem, NSObject, NSImage, NSApp, NSApplicationActivationPolicyRegular
from Cocoa import NSTimer
from Cocoa import NSPasteboard, NSStringPboardType, NSVariableStatusItemLength

from Cocoa import NSPanel, NSScreen, NSTextField, NSPanel, NSBorderlessWindowMask, NSImageView
from Cocoa import NSBorderlessWindowMask, NSWindowStyleMaskBorderless
from Cocoa import NSColor
from Cocoa import NSScrollView, NSTextView
from Cocoa import NSFont
from Cocoa import NSBox, NSBoxCustom, NSNoBorder
from Cocoa import NSBezierPath
from Cocoa import NSString
from Cocoa import NSFontAttributeName

import objc

import signal
import traceback
from time import sleep

# Custom panel for the quick entry window. This is neededto enable it to become 
# key window and main window

class QuickWindowPanel(NSPanel):
    def canBecomeKeyWindow(self):
        return True
    
    def canBecomeMainWindow(self):
        return True

class AppDelegate(NSObject):

    # Actions for various events

    def pb_init(self):
        self.pasteboard = NSPasteboard.generalPasteboard()

    def timerFired_(self, timer):
        if self.checkClipboard():
            self.status_item.setTitle_(MacLLMUI.status_working)
            # Read the clipboard content
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.1, self, 'doClipboardCallback:', None, False)

    def doClipboardCallback_(self, timer):
        self.macllm_ui.clipboardCallback()
        self.macllm_ui.pb_change_count = self.pasteboard.changeCount()
        self.status_item.setTitle_(MacLLMUI.status_ready)

    def terminate_(self, sender):
        NSApp().terminate_(self)

    # Check if the Clipboard has changed

    def checkClipboard(self):
        current_change_count = self.pasteboard.changeCount()
        if current_change_count != self.macllm_ui.pb_change_count:
            self.macllm_ui.pb_change_count = current_change_count
            return True
        else:
            return False
        
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

    def applicationDidFinishLaunching_(self, notification):
        try:
            self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(-1)
        
        # Set an icon for the status item
            self.status_item.setMenu_(self.menu())
            self.status_item.setTitle_(MacLLMUI.status_ready)
            self.status_item.setHighlightMode_(True)

            # Register a timer to check for new events
            NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                0.1, self, 'timerFired:', None, True)
            
            # Start tracking the clipboard
            self.pasteboard = NSPasteboard.generalPasteboard()
            self.macllm_ui.pb_change_count = self.pasteboard.changeCount()

        except Exception as e:
            # If we fail to initialize the status item, terminate the application and show stack trace
            print(f"Initialization failure: {e}")
            traceback.print_exc()
            NSApp().terminate_(self)


class WindowDelegate(NSObject):

    macllm_ui = None

    def initWithTextField_(self, text_field):
        self = objc.super(WindowDelegate, self).init()
        self.text_field = text_field
        self.text_field.setDelegate_(self)
        return self

    # React to special keys like escape, copy etc.  

    def control_textView_doCommandBySelector_(self, control, textView, commandSelector):
        if commandSelector == 'cancelOperation:':  
            # This handles Escape key. NSPanel does this automatically, but we need to do cleanup and
            # thus have to implement it here.
            self.macllm_ui.close_quick_window()
            return True
        elif commandSelector == 'noop:':  # Handle Command-C and Command-V
            current_event = NSApp().currentEvent()
            # Check for Command key (1 << 20)
            if current_event.modifierFlags() & (1 << 20):
                key = current_event.charactersIgnoringModifiers().lower()
                if key == 'c':  # Handle Command-C
                    self.macllm_ui.write_clipboard(self.text_field.stringValue())
                    self.macllm_ui.close_quick_window()
                    return True
                elif key == 'v':  # Handle Command-V
                    clipboard_content = self.macllm_ui.read_clipboard()
                    if clipboard_content:
                        self.text_field.setStringValue_(clipboard_content)
                    return True
        return False

    def textDidChange_(self, notification):
        print("textDidChange_")

    def controlTextDidEndEditing_(self, notification):
        # This gets called when Return is pressed
        text_field = notification.object()
        input_text = text_field.stringValue()
        self.macllm_ui.handle_user_input(input_text)

class MacLLMUI:

    # Layout of the window - updated to match specification
    padding = 4
    top_bar_height = 32
    text_area_width = 640   # Width for 80 characters
    input_field_height = 90  # 5 lines visible
    input_field_width = text_area_width
    window_corner_radius = 12.0
    text_corner_radius = 8.0
    fudge = 1 # no idea why this is needed, but it is

    # Everything below is calculated based on the above
    icon_width = 32  # Fixed icon size for top bar
    window_width = text_area_width + padding*2

    # Positioning for the three sections
    icon_x = padding + fudge
    text_area_x = padding + fudge
    input_field_x = padding + fudge

    # Define colors for the status icon
    status_ready   = "🟢 LLM"
    status_working = "🟠 LLM"

    # Text messages and error messages
    text_prompt = "How can I help you?"

    def __init__(self):
        self.app = None
        self.delegate = None
        self.macllm = None
        
        self.pb_change_count = 0
        self.clipboardCallback = self.dummy

        self.quick_window = None
        self.dock_image = NSImage.alloc().initByReferencingFile_("./assets/icon.png")
        self.logo_image = NSImage.alloc().initByReferencingFile_("./assets/icon32x32.png")

    def dummy(self):
        return

    @staticmethod
    def handle_interrupt(signal, frame):
        NSApp().terminate_(None)

    def iconStatus(self, color):
        self.delegate.status_item.button().setImage_(color)
        return

    def read_clipboard(self):
        content = self.delegate.pasteboard.stringForType_(NSStringPboardType)
        return content

    def write_clipboard(self, content):
        self.delegate.pasteboard.declareTypes_owner_([NSStringPboardType], None)
        self.delegate.pasteboard.setString_forType_(content, NSStringPboardType)

    def read_change_count(self):
        return self.delegate.pasteboard.changeCount()
    
    # This is called when the user presses Return in the pop-up window

    def handle_user_input(self, text):
        if text == "":
            return
        # Send the text to the LLM
        result = self.macllm.handle_instructions(text)
        # Update the text area with the full conversation after both user and assistant messages are added
        self.update_text_area(text)
        self.input_field.setStringValue_(result)

    def update_text_area(self, text):
        # Update with the full chat history
        formatted_history = self._format_chat_history()
        self.text_area.setStringValue_(formatted_history)
        # Force the text view to update
        self.text_area.needsDisplay = True
    
    def _format_chat_history(self):
        if hasattr(self.macllm, 'chat_history'):
            history = self.macllm.chat_history.get_history()
            formatted_history = []
            for role, text in history:
                if role == "user":
                    formatted_history.append(f"User: {text}")
                else:
                    formatted_history.append(f"Assistant: {text}")
            return "\n\n".join(formatted_history)
        else:
            return MacLLMUI.text_prompt

    def _calculate_minimum_text_height(self):
        """Calculate the minimum height needed to display the initial text content."""
        # Create a temporary NSTextView with the same width as our intended text area
        temp_text_view = NSTextView.alloc().initWithFrame_(((0, 0), (MacLLMUI.text_area_width - 2*MacLLMUI.text_corner_radius, 1000)))
        
        # Set the same font and text content
        temp_text_view.setFont_(NSFont.systemFontOfSize_(13.0))
        temp_text_view.setString_(MacLLMUI.text_prompt)
        
        # Get the layout manager to calculate the actual height with width constraints
        layout_manager = temp_text_view.layoutManager()
        text_container = temp_text_view.textContainer()
        
        if layout_manager and text_container:
            # Get the glyph range for the entire text
            glyph_range = layout_manager.glyphRangeForTextContainer_(text_container)
            
            # Calculate the bounding rect for the glyphs with width constraints
            bounding_rect = layout_manager.boundingRectForGlyphRange_inTextContainer_(glyph_range, text_container)
            return bounding_rect.size.height
        
        # Fallback to a reasonable minimum height
        return 200.0

    def open_quick_window(self):

        # Find the width and height of the screen
        screen_width = NSScreen.mainScreen().frame().size.width
        screen_height = NSScreen.mainScreen().frame().size.height
        
        # Calculate minimum text height using a temporary NSTextView
        minimum_text_height = self._calculate_minimum_text_height()
        
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
        icon_height = MacLLMUI.icon_width
        entry_height = MacLLMUI.input_field_height
        # There are 4 paddings: top, between top bar and main, between main and entry, bottom
        total_padding = padding * 4
        
        # Calculate optimal main area height based on minimum text height
        # Add some padding for the text container and scroll view
        text_container_padding = text_corner_radius * 2  # Padding inside the container
        optimal_main_area_height = minimum_text_height + text_container_padding
        
        # Calculate total window height needed
        total_ui_height = top_bar_height + optimal_main_area_height + entry_height + total_padding + padding_internal_fudge*2
        
        # Use the smaller of: optimal height or max window height
        window_height = min(total_ui_height, max_window_height)
        main_area_height = window_height - (top_bar_height + entry_height + total_padding + padding_internal_fudge*2)

        # --- Y COORDINATES ---
        # Y=0 is at the bottom
        input_field_y = padding
        main_area_y = input_field_y + entry_height + padding + padding_internal_fudge
        top_bar_y = window_height - padding - top_bar_height
        icon_y = top_bar_y  # Flush with top bar, no centering

        win = QuickWindowPanel.alloc()
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
        
        # Create an NSBox to serve as the rounded, colored background
        box = NSBox.alloc().initWithFrame_(((0, 0), (window_width+window_corner_radius, window_height+window_corner_radius)))
        box.setBoxType_(NSBoxCustom) 
        box.setBorderType_(NSNoBorder)  
        box.setCornerRadius_(window_corner_radius)
        #box.setTransparent_(True)
        box.setFillColor_(NSColor.colorWithCalibratedWhite_alpha_(0.7, 0.7))
        win.contentView().addSubview_(box)

        # Add image view (logo in top bar) as a subview of the box
        image_view = NSImageView.alloc().initWithFrame_(
            ((MacLLMUI.icon_x, icon_y), 
             (MacLLMUI.icon_width, MacLLMUI.icon_width))
        )
        image_view.setImage_(self.logo_image)
        image_view.setImageScaling_(3)  # NSScaleToFit = 3
        image_view.setContentHuggingPriority_forOrientation_(1000, 0)  # Horizontal
        image_view.setContentHuggingPriority_forOrientation_(1000, 1)  # Vertical
        box.addSubview_(image_view)

        # Main conversation area (middle section) as a scrollable NSTextView with rounded corners
        # Create a container view with rounded corners
        text_container = NSBox.alloc().initWithFrame_(
            ((MacLLMUI.text_area_x, main_area_y),
             (MacLLMUI.text_area_width, main_area_height))
        )
        text_container.setBoxType_(NSBoxCustom)
        text_container.setBorderType_(NSNoBorder)
        text_container.setCornerRadius_(text_corner_radius)
        text_container.setFillColor_(NSColor.whiteColor())
        box.addSubview_(text_container)

        # Create scroll view inside the container
        scroll_view = NSScrollView.alloc().initWithFrame_(
            ((0, 3), 
             (MacLLMUI.text_area_width - 2*text_corner_radius, main_area_height - 2*text_corner_radius))
        )
        scroll_view.setHasVerticalScroller_(True)
        scroll_view.setHasHorizontalScroller_(False)
        scroll_view.setAutohidesScrollers_(True)

        text_view = NSTextView.alloc().initWithFrame_(((textbox_x_fudge, textbox_y_fudge), (MacLLMUI.text_area_width - 2*text_corner_radius, main_area_height - 2*text_corner_radius)))
        text_view.setEditable_(False)
        text_view.setDrawsBackground_(False)  # Let the container handle the background
        
        # Initialize with chat history
        initial_text = self._format_chat_history()
        text_view.setString_(initial_text)
        self.text_area = text_view
        scroll_view.setDocumentView_(text_view)
        text_container.addSubview_(scroll_view)

        # Set font size for main text area
        text_view.setFont_(NSFont.systemFontOfSize_(13.0))
        main_font = text_view.font()
        if main_font is not None:
            print(f"Main text area font size: {main_font.pointSize()}")
        else:
            print("Main text area font is None")

        # Input field at bottom with rounded corners
        # Create a container view with rounded corners for the input field
        input_container = NSBox.alloc().initWithFrame_(
            ((MacLLMUI.input_field_x, input_field_y), 
             (MacLLMUI.input_field_width, MacLLMUI.input_field_height))
        )
        input_container.setBoxType_(NSBoxCustom)
        input_container.setBorderType_(NSNoBorder)
        input_container.setCornerRadius_(text_corner_radius)
        input_container.setFillColor_(NSColor.whiteColor())
        box.addSubview_(input_container)

        # Create input field inside the container
        input_field = NSTextField.alloc().initWithFrame_(
            ((textbox_x_fudge, textbox_y_fudge), 
             (MacLLMUI.input_field_width - 2*text_corner_radius, MacLLMUI.input_field_height - 2*text_corner_radius))
        )
        input_field.setStringValue_("")
        input_field.setFont_(NSFont.systemFontOfSize_(13.0))
        input_field.setDrawsBackground_(False)  # Let the container handle the background
        self.window_delegate = WindowDelegate.alloc().initWithTextField_(input_field)
        self.window_delegate.macllm_ui = self
        input_field.setDelegate_(self.window_delegate)
        input_container.addSubview_(input_field)
        self.input_field = input_field

        input_font = input_field.font()
        if input_font is not None:
            print(f"Input field font size: {input_font.pointSize()}")
        else:
            print("Input field font is None")

        # Move the window to the front and activate it
        win.display()
        win.orderFrontRegardless()
        win.makeKeyWindow()  # Make it the key window
        self.app.activateIgnoringOtherApps_(True)
        self.input_field.becomeFirstResponder()  # Set focus to the input field

    def close_quick_window(self):
        self.quick_window.orderOut_(None)
        self.quick_window = None
        # Deactivate our app to return focus to the previous application
        self.app.hide_(None)
    
    # Handle the hotkey press
    def hotkey_pressed(self):
        if self.quick_window is None:
            self.open_quick_window()
        else:
            self.close_quick_window()

    def start(self):
        # Pointer to main class, we need this for callback
        signal.signal(signal.SIGINT, self.handle_interrupt)

        self.app = NSApplication.sharedApplication()
        self.delegate = AppDelegate.alloc().init()
        self.delegate.macllm_ui = self
        self.app.setDelegate_(self.delegate)
        self.app.setActivationPolicy_(NSApplicationActivationPolicyRegular)

        self.delegate.pb_init()
        self.pb_change_count = self.read_change_count()
        
        # Change the App icon
        # Only set the icon if the image is valid (has non-zero size)
        if self.dock_image.size().width > 0 and self.dock_image.size().height > 0:
            self.app.setApplicationIconImage_(self.dock_image)

        # Start the application event loop
        self.app.run()

