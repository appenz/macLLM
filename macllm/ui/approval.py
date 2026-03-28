"""Inline approval prompt rendering and keyboard handling for shell commands."""

from __future__ import annotations

from Cocoa import (
    NSAttributedString,
    NSColor,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSLinkAttributeName,
    NSUnderlineStyleAttributeName,
    NSUnderlineStyleSingle,
)


class ApprovalRenderer:
    """Renders and manages inline command approval prompts."""

    # Shared color definitions
    _muted = None
    _light = None
    _green = None
    _red = None
    _orange = None
    _font_sm = None
    _font_sm_bold = None
    _font_mono = None

    @classmethod
    def _init_styles(cls):
        if cls._muted is not None:
            return
        cls._muted = NSColor.colorWithCalibratedWhite_alpha_(0.50, 1.0)
        cls._light = NSColor.colorWithCalibratedWhite_alpha_(0.62, 1.0)
        cls._green = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.30, 0.69, 0.31, 1.0)
        cls._red = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.84, 0.24, 0.24, 1.0)
        cls._orange = NSColor.colorWithCalibratedRed_green_blue_alpha_(0.90, 0.60, 0.20, 1.0)
        cls._font_sm = NSFont.systemFontOfSize_(11.0)
        cls._font_sm_bold = NSFont.boldSystemFontOfSize_(11.0)
        cls._font_mono = NSFont.monospacedSystemFontOfSize_weight_(10.0, 0.0)

    @classmethod
    def render_pending(cls, text_storage, pending):
        """Render the multi-line approval prompt into *text_storage*."""
        cls._init_styles()

        def _append(text, color, font=None, underline=False):
            attrs = {
                NSForegroundColorAttributeName: color,
                NSFontAttributeName: font or cls._font_sm,
            }
            if underline:
                attrs[NSUnderlineStyleAttributeName] = NSUnderlineStyleSingle
            a = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
            text_storage.appendAttributedString_(a)

        cmd_display = pending.command
        if len(cmd_display) > 80:
            cmd_display = cmd_display[:77] + "..."

        has_unknown_exe = bool(pending.unknown_executables)
        has_ungranted = bool(getattr(pending, "ungranted_paths", None))

        _append("  ┌ Shell: ", cls._muted, cls._font_sm_bold)
        _append(f"{cmd_display}\n", cls._light, cls._font_mono)

        if has_unknown_exe:
            exe_list = ", ".join(pending.unknown_executables)
            _append(f"  │ ⚠ {exe_list} not on the allowlist\n", cls._orange)

        if has_ungranted:
            import os
            home = os.path.expanduser("~")
            display_paths = []
            for p in pending.ungranted_paths:
                if p.startswith(home):
                    display_paths.append("~" + p[len(home):] or "~")
                else:
                    display_paths.append(p)
            path_list = ", ".join(display_paths)
            _append(f"  │ ⚠ Needs access to: {path_list}\n", cls._orange)

        if has_unknown_exe:
            exe_list = ", ".join(pending.unknown_executables)
            _append("  │ [", cls._muted)
            _append("R", cls._light, cls._font_sm_bold, underline=True)
            _append("]un once  [", cls._muted)
            _append("D", cls._light, cls._font_sm_bold, underline=True)
            _append("]eny  [", cls._muted)
            _append("A", cls._light, cls._font_sm_bold, underline=True)
            _append("]lways allow '", cls._muted)
            _append(exe_list, cls._light)
            _append("'\n", cls._muted)
        else:
            _append("  │ [", cls._muted)
            _append("R", cls._light, cls._font_sm_bold, underline=True)
            _append("]un (grant & run)  [", cls._muted)
            _append("D", cls._light, cls._font_sm_bold, underline=True)
            _append("]eny\n", cls._muted)

    @classmethod
    def render_resolved(cls, text_storage, entry):
        """Render the collapsed post-decision line(s)."""
        cls._init_styles()

        def _append(text, color, font=None):
            a = NSAttributedString.alloc().initWithString_attributes_(
                text,
                {
                    NSForegroundColorAttributeName: color,
                    NSFontAttributeName: font or cls._font_sm,
                },
            )
            text_storage.appendAttributedString_(a)

        cmd = entry.args_summary.strip('"')

        if entry.status == "success":
            _append("  ✓ ", cls._green, cls._font_sm_bold)
            _append(f"Shell: {cmd}\n", cls._muted)
            if entry.result_summary and "added to allowlist" in entry.result_summary:
                _append(f"    {entry.result_summary}\n", cls._muted)
        elif entry.status == "error":
            _append("  ✗ ", cls._red, cls._font_sm_bold)
            _append(f"Shell: {cmd}", cls._muted)
            if entry.result_summary:
                _append(f" — {entry.result_summary}", cls._red)
            _append("\n", cls._muted)

    @classmethod
    def render_output(cls, text_storage, entry):
        """Render command output as an expandable block (3-line preview)."""
        cls._init_styles()

        output = entry.full_output
        if not output:
            return

        lines = output.split("\n")
        max_preview = 3

        if entry.expanded:
            display_lines = lines
        else:
            display_lines = lines[:max_preview]

        def _append(text, color, font=None):
            a = NSAttributedString.alloc().initWithString_attributes_(
                text,
                {
                    NSForegroundColorAttributeName: color,
                    NSFontAttributeName: font or cls._font_mono,
                },
            )
            text_storage.appendAttributedString_(a)

        for line in display_lines:
            _append(f"    {line}\n", cls._light)

        if not entry.expanded and len(lines) > max_preview:
            remaining = len(lines) - max_preview
            link_text = f"    ▸ {remaining} more lines\n"
            attrs = {
                NSForegroundColorAttributeName: cls._muted,
                NSFontAttributeName: cls._font_sm,
                NSLinkAttributeName: f"macllm://toggle-output/{entry.id}",
            }
            a = NSAttributedString.alloc().initWithString_attributes_(link_text, attrs)
            text_storage.appendAttributedString_(a)
        elif entry.expanded and len(lines) > max_preview:
            link_text = "    ▾ collapse\n"
            attrs = {
                NSForegroundColorAttributeName: cls._muted,
                NSFontAttributeName: cls._font_sm,
                NSLinkAttributeName: f"macllm://toggle-output/{entry.id}",
            }
            a = NSAttributedString.alloc().initWithString_attributes_(link_text, attrs)
            text_storage.appendAttributedString_(a)

    @classmethod
    def handle_key(cls, key: str, status_mgr) -> bool:
        """Handle a keypress while an approval is pending.

        Returns ``True`` if the key was consumed.
        """
        if status_mgr.pending_approval is None:
            return False

        key_lower = key.lower()
        if key_lower == "r":
            status_mgr.resolve_approval("run")
            return True
        if key_lower == "d":
            status_mgr.resolve_approval("deny")
            return True
        if key_lower == "a":
            status_mgr.resolve_approval("always_allow")
            return True

        return False
