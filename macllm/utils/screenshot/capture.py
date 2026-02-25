"""Capture a screenshot of a specific macOS window using Quartz APIs."""

import Quartz
from AppKit import NSBitmapImageRep, NSPNGFileType


def find_window(title_substring: str) -> int | None:
    """Find a visible window whose title contains *title_substring*.

    Returns the CGWindowID for the first match, or ``None``.
    """
    window_list = Quartz.CGWindowListCopyWindowInfo(
        Quartz.kCGWindowListOptionOnScreenOnly, Quartz.kCGNullWindowID
    )
    for w in window_list:
        name = w.get("kCGWindowName") or ""
        if title_substring in name:
            return w.get("kCGWindowNumber")
    return None


def capture_window(window_id: int, output_path: str) -> bool:
    """Capture *window_id* and write a PNG to *output_path*.

    Returns ``True`` on success, ``False`` otherwise.
    """
    cg_image = Quartz.CGWindowListCreateImage(
        Quartz.CGRectNull,
        Quartz.kCGWindowListOptionIncludingWindow,
        window_id,
        Quartz.kCGWindowImageBoundsIgnoreFraming,
    )
    if cg_image is None:
        return False

    bitmap = NSBitmapImageRep.alloc().initWithCGImage_(cg_image)
    png_data = bitmap.representationUsingType_properties_(NSPNGFileType, None)
    if png_data is None:
        return False

    png_data.writeToFile_atomically_(output_path, True)
    return True


def capture_window_by_title(title_substring: str, output_path: str) -> bool:
    """Find a window by *title_substring* and save a PNG screenshot.

    Convenience wrapper around :func:`find_window` + :func:`capture_window`.
    """
    wid = find_window(title_substring)
    if wid is None:
        return False
    return capture_window(wid, output_path)
