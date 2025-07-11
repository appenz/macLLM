from quickmachotkey import quickHotKey, mask
from quickmachotkey.constants import kVK_ANSI_A, cmdKey, controlKey
from AppKit import NSApplication
from PyObjCTools import AppHelper

@quickHotKey(virtualKey=kVK_ANSI_A, modifierMask=mask(cmdKey, controlKey))
def handler() -> None:
    print("handled ⌘⌃A")

if __name__ == "__main__":
    app = NSApplication.sharedApplication()
    print("running")
    AppHelper.runEventLoop()
