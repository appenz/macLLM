#
# Simple program that creates a menu bar icon with PyObjC
#

from Foundation import NSThread 


from Cocoa import NSApplication, NSStatusBar, NSMenu, NSMenuItem, NSObject, NSImage, NSApp, NSApplicationActivationPolicyRegular
from Cocoa import NSTimer
from Cocoa import NSPasteboard, NSStringPboardType, NSVariableStatusItemLength

from Cocoa import NSPanel, NSScreen, NSTextField, NSPanel, NSBorderlessWindowMask, NSImageView
from Cocoa import NSBorderlessWindowMask, NSWindowStyleMaskBorderless

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

    #                              <----------------------- input_field_width --------------------------->
    #                                                   (same as text_area_width)
    # +--------------------------------------------------------------------------------------------------+
    # |                                                                                                  |
    # |    +------------------+    +----------------------------------------------------------------+    |
    # |    |                  |    |                                                         A      |    |
    # |    |                  |    |  Text Area ("How can I help you?")  text_area_height    |      |    |
    # |    |                  |    |                                                         V      |    |
    # |    |       Icon       |    +----------------------------------------------------------------+    |
    # |    |  <- auto-size -> |                                                                          |
    # |    |  based on window |    |----------------------------------------------------------------|    |
    # |    |                  |    |                                                         A      |    |
    # |    |                  |    |  Input Field                       input_field_height   |      |    |
    # |    |                  |    |                                                         V      |    |
    # |    +------------------+    +----------------------------------------------------------------+    |
    # |                                                                                                  |
    # +--------------------------------------------------------------------------------------------------+

    # Layout of the window
    text_area_height = 35
    text_area_width = 600
    input_field_height = 60
    input_field_width = text_area_width
    padding = 10

    # Everything below is calculated based on the above
    window_height = input_field_height + text_area_height + padding*3
    icon_width = window_height-padding*2
    icon_padding = padding
    window_width = icon_width + input_field_width + padding*3

    input_field_x = icon_width + padding*2
    input_field_y = padding
    text_area_x   = icon_width + padding*2
    text_area_y   = padding + input_field_height + padding

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
        self.update_text_area(text)
        self.input_field.setStringValue_(result)

    def update_text_area(self, text):
        self.text_area.setStringValue_(text)

    def open_quick_window(self):

        # Find the width and height of the screen
        screen_width = NSScreen.mainScreen().frame().size.width
        screen_height = NSScreen.mainScreen().frame().size.height
        
        win = QuickWindowPanel.alloc()
        self.quick_window = win

        # Open a window without a title bar
        frame = ( 
                  ( (screen_width-MacLLMUI.window_width) / 2, 
                     screen_height *0.7 - MacLLMUI.window_height/2
                  ), (MacLLMUI.window_width, MacLLMUI.window_height) 
                ) 
        window_mask = NSBorderlessWindowMask
        win.initWithContentRect_styleMask_backing_defer_(frame, window_mask, 2, 0)
        win.setTitle_("🦙 macLLM")
        win.setLevel_(3)  # floating window

        # Add image view
        image_view = NSImageView.alloc().initWithFrame_(
            ((MacLLMUI.icon_padding, MacLLMUI.icon_padding), 
             (MacLLMUI.icon_width, MacLLMUI.icon_width))
        )
        image_view.setImage_(self.dock_image)
        image_view.setImageScaling_(3)  # NSScaleToFit = 3
        image_view.setContentHuggingPriority_forOrientation_(1000, 0)  # Horizontal
        image_view.setContentHuggingPriority_forOrientation_(1000, 1)  # Vertical
        win.contentView().addSubview_(image_view)

        # Adjust text area position and width
        # Adjust text area position and width
        text_area = NSTextField.alloc().initWithFrame_(
            ((MacLLMUI.text_area_x, MacLLMUI.text_area_y), 
             (MacLLMUI.text_area_width, MacLLMUI.text_area_height))
        )
        text_area.setStringValue_(MacLLMUI.text_prompt)
        text_area.setEditable_(False)
        text_area.setBezeled_(False)
        text_area.setDrawsBackground_(False)
        self.text_area = text_area
        win.contentView().addSubview_(text_area)

        # Adjust input field position and width
        input_field = NSTextField.alloc().initWithFrame_(
            ((MacLLMUI.input_field_x, MacLLMUI.input_field_y), 
             (MacLLMUI.input_field_width, MacLLMUI.input_field_height))
        )
        input_field.setStringValue_("")
        self.window_delegate = WindowDelegate.alloc().initWithTextField_(input_field)
        self.window_delegate.macllm_ui = self
        input_field.setDelegate_(self.window_delegate)
        win.contentView().addSubview_(input_field)
        self.input_field = input_field

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
        self.dock_image = NSImage.alloc().initByReferencingFile_("./assets/icon.png")
        self.app.setApplicationIconImage_(self.dock_image)

        # Start the application event loop
        self.app.run()

