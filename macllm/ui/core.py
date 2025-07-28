#
# Simple program that creates a menu bar icon with PyObjC
#

from Foundation import NSThread 


from Cocoa import NSApplication, NSStatusBar, NSMenu, NSMenuItem, NSObject, NSImage, NSApp, NSApplicationActivationPolicyRegular
from Cocoa import NSTimer
from Cocoa import NSPasteboard, NSStringPboardType

from Cocoa import NSPanel, NSScreen, NSPanel, NSBorderlessWindowMask, NSImageView
from Cocoa import NSBorderlessWindowMask
from Cocoa import NSColor
from Cocoa import NSScrollView, NSTextView
from Cocoa import NSFont
from Cocoa import NSBox, NSBoxCustom, NSNoBorder
from Cocoa import NSFontAttributeName, NSForegroundColorAttributeName, NSParagraphStyleAttributeName
from Cocoa import NSMutableParagraphStyle
from Cocoa import NSGraphicsContext
from Cocoa import NSMutableAttributedString

from macllm.ui.main_text import MainTextHandler
from macllm.ui.input_field import InputFieldHandler

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




class MacLLMUI:

    # Font
    font_size = 13.0

    # Layout of the window - updated to match specification
    padding = 4
    top_bar_height = 48  # Updated to match new specification
    text_area_width = 640   # Width for 80 characters
    input_field_height = 90  # 5 lines visible
    input_field_width = text_area_width
    window_corner_radius = 12.0
    text_corner_radius = 8.0
    fudge = 1 # no idea why this is needed, but it is

    # Everything below is calculated based on the above
    icon_width = 38  # Fixed icon size for top bar
    window_width = text_area_width + padding*2

    # Top bar positioning and sizing
    top_bar_text_field_width = 80  # Width of the text field in top bar
    icon_x = padding + fudge
    text_area_x = padding + fudge
    input_field_x = padding + fudge

    # Define colors for the status icon
    status_ready   = "🟢 LLM"
    status_working = "🟠 LLM"

    # Colors
    white = NSColor.whiteColor()
    light_grey = NSColor.colorWithCalibratedWhite_alpha_(0.9, 1.0)
    dark_grey  = NSColor.colorWithCalibratedWhite_alpha_(0.8, 1.0)
    text_grey  = NSColor.colorWithCalibratedWhite_alpha_(0.5, 1.0)
    text_grey_subtle  = NSColor.colorWithCalibratedWhite_alpha_(0.65, 1.0)

    def __init__(self):
        self.app = None
        self.delegate = None
        self.macllm = None
        
        self.pb_change_count = 0
        self.clipboardCallback = self.dummy

        self.quick_window = None
        self.dock_image = NSImage.alloc().initByReferencingFile_("./assets/icon.png")
        self.logo_image = NSImage.alloc().initByReferencingFile_("./assets/icon-nobg.png")
        
        # Create a high-quality scaled version of the logo for the top bar
        self._create_scaled_logo()

    def dummy(self):
        return

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
        # Resize window to fit new content (this also updates the text area)
        self.update_window()
        # Clear the input field for the next message
        InputFieldHandler.clear_input_field(self.input_field)

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

        if self.quick_window is None:
            new_window = True
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

        # ----- Top bar with dark grey container, icon, context area, and text field ---------------------------------------------------------------

        # Create or update the top bar container
        if new_window:
            # Create dark grey NSBox container for top bar
            top_bar_container = NSBox.alloc().initWithFrame_(
                ((MacLLMUI.text_area_x, top_bar_y), 
                 (MacLLMUI.text_area_width, MacLLMUI.top_bar_height))
            )
            top_bar_container.setBoxType_(NSBoxCustom)
            top_bar_container.setBorderType_(NSNoBorder)
            top_bar_container.setCornerRadius_(text_corner_radius)
            top_bar_container.setFillColor_(MacLLMUI.dark_grey)
            box.addSubview_(top_bar_container)
            self.top_bar_container = top_bar_container
        else:
            # Update existing top bar container frame
            top_bar_container = self.top_bar_container
            top_bar_container.setFrame_(((MacLLMUI.text_area_x, top_bar_y), 
                                        (MacLLMUI.text_area_width, MacLLMUI.top_bar_height)))

        # Calculate positions within the top bar container
        top_bar_internal_padding = 8  # Internal padding within the top bar
        icon_x_internal = 0
        # Vertically centre icon and text inside the 48-px bar
        icon_y = int((MacLLMUI.top_bar_height - MacLLMUI.icon_width) / 2)-5
        text_y = icon_y
        text_height = MacLLMUI.top_bar_height - text_y-10

        context_area_x = icon_x_internal + MacLLMUI.icon_width + top_bar_internal_padding
        text_field_x = MacLLMUI.text_area_width - MacLLMUI.top_bar_text_field_width - top_bar_internal_padding

        if new_window:
            # Add image view (logo in top bar) as a subview of the top bar container
            image_view = NSImageView.alloc().initWithFrame_(
                ((icon_x_internal, icon_y), 
                 (MacLLMUI.icon_width, MacLLMUI.icon_width))
            )
            image_view.setImage_(self.logo_image)
            image_view.setImageScaling_(3)  # NSScaleToFit = 3
            image_view.setImageAlignment_(1)  # NSImageAlignCenter = 1
            image_view.setImageFrameStyle_(0)  # NSImageFrameNone = 0
            image_view.setAnimates_(False)
            image_view.setContentHuggingPriority_forOrientation_(1000, 0)  # Horizontal
            image_view.setContentHuggingPriority_forOrientation_(1000, 1)  # Vertical
            top_bar_container.addSubview_(image_view)
            self.logo_image_view = image_view

            # Create text view in top bar (flush right) for multiple lines
            top_bar_text_view = NSTextView.alloc().initWithFrame_(
                ((text_field_x, text_y), 
                 (MacLLMUI.top_bar_text_field_width, text_height))
            )
            top_bar_text_view.setString_("")
            top_bar_text_view.setDrawsBackground_(False)
            top_bar_text_view.setEditable_(False)  # Read-only for now
            top_bar_text_view.setSelectable_(False)  # Not selectable
            # Remove default text container inset so lines stick to the right/ top equally
            top_bar_text_view.setTextContainerInset_((0.0, 0.0))
            
            # Set right alignment and styling for the text
            paragraph_style = NSMutableParagraphStyle.alloc().init()
            paragraph_style.setAlignment_(2)  # NSRightTextAlignment = 2
            text_attributes = {
                NSFontAttributeName: NSFont.systemFontOfSize_(11.0),
                NSForegroundColorAttributeName: MacLLMUI.text_grey_subtle,
                NSParagraphStyleAttributeName: paragraph_style
            }
            top_bar_text_view.setTypingAttributes_(text_attributes)
            top_bar_container.addSubview_(top_bar_text_view)
            self.top_bar_text_view = top_bar_text_view
        else:
            # Update existing image view position
            image_view = self.logo_image_view
            image_view.setFrame_(((icon_x_internal, icon_y), 
                                 (MacLLMUI.icon_width, MacLLMUI.icon_width)))
            
            # Update existing text view position
            top_bar_text_view = self.top_bar_text_view
            top_bar_text_view.setFrame_(((text_field_x, text_y), 
                                        (MacLLMUI.top_bar_text_field_width, text_height)))
            top_bar_text_view.setTextContainerInset_((0.0, 0.0))


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

        if new_window:
            scroll_view = NSScrollView.alloc().initWithFrame_(
                ((0, 3),
                (MacLLMUI.text_area_width - 2*text_corner_radius, main_area_height - 2*text_corner_radius))
            )

            scroll_view.setHasVerticalScroller_(True)
            scroll_view.setHasHorizontalScroller_(False)
            scroll_view.setAutohidesScrollers_(True)
            self.scroll_view = scroll_view

            text_view = NSTextView.alloc().initWithFrame_(((textbox_x_fudge, textbox_y_fudge), (MacLLMUI.text_area_width - 2*text_corner_radius, main_area_height - 2*text_corner_radius)))
            text_view.setEditable_(False)
            text_view.setDrawsBackground_(False)  # Let the container handle the background
            text_view.setFont_(NSFont.systemFontOfSize_(MacLLMUI.font_size))
            self.text_area = text_view

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

        MainTextHandler.set_text_content(self.macllm, text_view)

        # Update the top bar text with model and token information
        self.update_top_bar_text()

        # ----- Input field at bottom with rounded corners ---------------------------------------------------------------

        if new_window:
            # Create input field using the new handler
            (input_container, input_field, delegate) = InputFieldHandler.create_input_field(
                box, (0, input_field_y), self)
            self.input_container = input_container
            self.input_field = input_field
            self.window_delegate = delegate

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

    def update_top_bar_text(self):
        if not hasattr(self, "top_bar_text_view"):
            return

        provider, model = self.macllm.llm.get_provider_model()
        tokens   = self.macllm.llm.get_token_count()

        # Create the full text
        txt = f"{provider}\n{model}\n{tokens} tkns"

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
        
        # Apply provider style to the first line (provider name)
        provider_range = (0, len(provider))
        attr_str.addAttributes_range_(attrs_provider_name, provider_range)
        
        # Apply rest of text style to everything after the provider
        rest_range = (len(provider), len(txt) - len(provider))
        attr_str.addAttributes_range_(attrs_rest_of_text, rest_range)
        
        self.top_bar_text_view.textStorage().setAttributedString_(attr_str)

    def close_window(self):
        self.quick_window.orderOut_(None)
        self.quick_window = None
        # Deactivate our app to return focus to the previous application
        self.app.hide_(None)
    
    # Handle the hotkey press
    def hotkey_pressed(self):
        if self.quick_window is None:
            self.update_window()
        else:
            self.close_window()

    def start(self, dont_run_app: bool = False):
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

        # Start the application event loop (unless in test mode)
        if not dont_run_app:
            self.app.run()

