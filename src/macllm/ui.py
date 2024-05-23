#
# Simple program that creates a menu bar icon with PyObjC
#

from Cocoa import NSApplication, NSStatusBar, NSStatusItem, NSVariableStatusItemLength, NSMenu, NSMenuItem, NSObject, NSImage, NSApp, NSApplicationActivationPolicyRegular
from Cocoa import NSTimer

from Cocoa import NSImageNameStatusAvailable, NSImageNameStatusNone, NSImageNameStatusPartiallyAvailable, NSImageNameStatusUnavailable
from PyObjCTools import AppHelper

import signal
        
class AppDelegate(NSObject):

    def timerFired_(self, timer):
        self.MacLLMUI.main_loop

    def terminate_(self, sender):
        NSApp().terminate_(self)

    def options_(self, sender):
        print("Options clicked!")
    
    def applicationDidFinishLaunching_(self, notification):
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)
        
        # Set an icon for the status item
        iconStatus(self, MacLLMUI.green)
        
        # Create a menu
        self.menu = NSMenu.alloc().init()
        
        # Add items to the menu
        options_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Options", "options:", "")
        self.menu.addItem_(options_item)

        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "terminate:", "")
        self.menu.addItem_(quit_item)
        
        # Set the menu to the status item
        self.status_item.setMenu_(self.menu)

        self.timer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            1.0, self, 'timerFired:', None, True)    

class MacLLMUI:

    green = NSImageNameStatusAvailable
    red = NSImageNameStatusUnavailable
    yellow = NSImageNameStatusPartiallyAvailable
    grey = NSImageNameStatusNone

    def __init__(self):
        self.app = None
        self.delegate = None
        self.icon_color = "green"
        self.macllm = None
    
    @staticmethod
    def handle_interrupt(signal, frame):
        NSApp().terminate_(None)

    def iconStatus(d, color):
        d.status_item.button().setImage_(icon)

    def start(self, macllm):
        # Pointer to main class, we need this for callback
        self.macllm = macllm
        signal.signal(signal.SIGINT, self.handle_interrupt)

        self.app = NSApplication.sharedApplication()
        self.delegate = AppDelegate.alloc().init()
        self.delegate.MacLLMUI = self
        self.app.setDelegate_(self.delegate)
        self.app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
        
        # Start the application event loop
        self.app.run()

