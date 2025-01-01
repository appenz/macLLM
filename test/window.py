#
# Open a simple window with an input field and a button using PyObjC
#

from Cocoa import NSObject, NSApplication, NSApp, NSWindow, NSButton, NSSound, NSScreen, NSTextField
from PyObjCTools import AppHelper


class AppDelegate(NSObject):
    def applicationDidFinishLaunching_(self, aNotification):
        print("Hello, World!")

    def sayHello_(self, sender):
        print("Hello again, World!")


def main():
    app = NSApplication.sharedApplication()

    # we must keep a reference to the delegate object ourselves,
    # NSApp.setDelegate_() doesn't retain it. A local variable is
    # enough here.
    delegate = AppDelegate.alloc().init()
    NSApp().setDelegate_(delegate)

    # Find the width and height of the screen
    screen_width = NSScreen.mainScreen().frame().size.width
    screen_height = NSScreen.mainScreen().frame().size.height

    win = NSWindow.alloc()
    frame = ((screen_width / 2 - 125, screen_height *0.7 - 50), (250.0, 100.0))
    win.initWithContentRect_styleMask_backing_defer_(frame, 15, 2, 0)
    win.setTitle_("🦙 macLLM - What should I do?")
    win.setLevel_(3)  # floating window

    # Add a text field
    text_field = NSTextField.alloc().initWithFrame_(((10.0, 10.0), (230.0, 80.0)))
    win.contentView().addSubview_(text_field)
    text_field.setStringValue_("What should I do?")

    bye = NSButton.alloc().initWithFrame_(((100.0, 10.0), (80.0, 80.0)))
    win.contentView().addSubview_(bye)
    bye.setBezelStyle_(4)
    bye.setTarget_(app)
    bye.setAction_("stop:")
    bye.setEnabled_(1)
    bye.setTitle_("Goodbye!")

    win.display()
    win.orderFrontRegardless()  # but this one does

    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()