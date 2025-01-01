from Cocoa import NSPasteboard, NSStringPboardType, NSString

def write_clipboard(text):
    pasteboard = NSPasteboard.generalPasteboard()
    pasteboard.declareTypes_owner_([NSStringPboardType], None)
    pasteboard.setString_forType_(text, NSStringPboardType)

if __name__ == "__main__":
    text_to_write = "Hello, macOS Clipboard!"
    write_clipboard(text_to_write)
    print("Text written to clipboard:", text_to_write)