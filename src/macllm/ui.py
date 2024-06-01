#
# Simple program that creates a menu bar icon with PyObjC
#

from Cocoa import NSApplication, NSStatusBar, NSStatusItem, NSVariableStatusItemLength, NSMenu, NSMenuItem, NSObject, NSImage, NSApp, NSApplicationActivationPolicyRegular
from Cocoa import NSTimer
from Cocoa import NSPasteboard, NSStringPboardType

from Foundation import NSThread 

from Cocoa import NSImageNameStatusAvailable, NSImageNameStatusNone, NSImageNameStatusPartiallyAvailable, NSImageNameStatusUnavailable
from PyObjCTools import AppHelper
from Foundation import NSBundle

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


class MacLLMUI:

    # Define colors for the status icon
    status_ready   = "🟢 LLM"
    status_working = "🟠 LLM"

    def __init__(self):
        self.app = None
        self.delegate = None
        self.macllm = None
        
        self.pb_change_count = 0
        self.clipboardCallback = self.dummy

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

