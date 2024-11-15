#
# Simple program that creates a menu bar icon with PyObjC
#

from Foundation import NSThread 


from Cocoa import NSApplication, NSStatusBar, NSStatusItem, NSVariableStatusItemLength, NSMenu, NSMenuItem, NSObject, NSImage, NSApp, NSApplicationActivationPolicyRegular
from Cocoa import NSTimer
from Cocoa import NSPasteboard, NSStringPboardType

from Cocoa import NSImageNameStatusAvailable, NSImageNameStatusNone, NSImageNameStatusPartiallyAvailable, NSImageNameStatusUnavailable

from Cocoa import NSWindow, NSButton, NSScreen, NSTextField

from PyObjCTools import AppHelper
from Foundation import NSBundle

import objc

import signal
import traceback
from time import sleep

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
            # Set an icon for the status item
            self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(-1)
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
        if commandSelector == 'cancelOperation:':  # This handles Escape key
            self.macllm_ui.close_quick_window()
            return True
        elif commandSelector == 'noop:':  # Handle Command-C
            current_event = NSApp().currentEvent()
            # Check for Command key (1 << 20) and 'c' key (0x63)
            if (current_event.modifierFlags() & (1 << 20) and 
                current_event.charactersIgnoringModifiers().lower() == 'c'):
                self.macllm_ui.write_clipboard(self.text_field.stringValue())
                self.macllm_ui.close_quick_window()
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

    # Define colors for the status icon
    status_ready   = "🟢 LLM"
    status_working = "🟠 LLM"

    # Layout of the window
    top_padding = 4
    text_area_height = 40
    input_field_height = 60
    window_width = 600
    window_height = input_field_height + text_area_height

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
        print(f"User input: {text}")
        result = self.macllm.handle_instructions(text)
        self.update_text_area(text)
        self.input_field.setStringValue_(result)

    def update_text_area(self, text):
        self.text_area.setStringValue_(text)

    def open_quick_window(self):

        # Find the width and height of the screen
        screen_width = NSScreen.mainScreen().frame().size.width
        screen_height = NSScreen.mainScreen().frame().size.height

        win = NSWindow.alloc()
        self.quick_window = win

        frame = ( ( (screen_width-MacLLMUI.window_width) / 2, screen_height *0.7 - MacLLMUI.window_height/2), (MacLLMUI.window_width, MacLLMUI.window_height) ) 
        win.initWithContentRect_styleMask_backing_defer_(frame, 15, 2, 0)
        win.setTitle_("🦙 macLLM")
        win.setLevel_(3)  # floating window

        # Rename label to text_area
        text_area = NSTextField.alloc().initWithFrame_(((10.0, MacLLMUI.window_height - MacLLMUI.text_area_height - MacLLMUI.top_padding), (MacLLMUI.window_width-20, MacLLMUI.text_area_height)))
        text_area.setStringValue_(MacLLMUI.text_prompt)
        text_area.setEditable_(False)
        text_area.setBezeled_(False)
        text_area.setDrawsBackground_(False)
        self.text_area = text_area
        win.contentView().addSubview_(text_area)

        # Add the text input field
        input_field = NSTextField.alloc().initWithFrame_(((10.0, 10.0), (MacLLMUI.window_width-20, MacLLMUI.input_field_height)))
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
    
    # Handle the hotkey press
    def hotkey_pressed(self):
        print("Hotkey pressed ⌘⌃A")
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
        self.dock_image = NSImage.alloc().initByReferencingFile_("/Users/gappenzeller/dev/macLLM/assets/icon.png")
        self.app.setApplicationIconImage_(self.dock_image)

        # Start the application event loop
        self.app.run()

