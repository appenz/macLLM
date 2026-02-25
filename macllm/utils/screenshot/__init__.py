"""Capture a screenshot of a specific macOS window using Quartz APIs.

Public API:
    find_window(title_substring)              -> window_id or None
    capture_window(window_id, path)           -> True on success
    capture_window_by_title(title, path)      -> True on success
"""

from .capture import find_window, capture_window, capture_window_by_title

__all__ = ["find_window", "capture_window", "capture_window_by_title"]
