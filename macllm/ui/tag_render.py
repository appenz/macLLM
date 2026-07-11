from __future__ import annotations

"""Shared helpers for rendering tags/shortcuts as blue pills.

Functions here are used by both the input field and the history view so
visuals and token rules remain consistent across the app.
"""

from typing import Iterable, Tuple

from macllm.markdown.blocks import FONT_SIZE
from Cocoa import (
    NSAttributedString,
    NSMutableAttributedString,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSAttachmentAttributeName,
    NSImage,
    NSBezierPath,
    NSColor,
    NSMakeRect,
)
import objc
from urllib.parse import urlparse


# Attribute name used to store the raw underlying tag/shortcut text on the pill
TAG_ATTR_NAME = "macLLMTagString"


class _InlineTextAttachment(objc.lookUpClass("NSTextAttachment")):
    """NSTextAttachment with adjustable vertical offset for baseline fit."""

    _verticalOffset = 0.0

    def setVerticalOffset_(self, value):  # noqa: N802
        self._verticalOffset = value

    def attachmentBoundsForTextContainer_proposedLineFragment_glyphPosition_characterIndex_(
        self, textContainer, lineFrag, position, charIndex
    ):  # noqa: N802
        rect = objc.super(_InlineTextAttachment, self).attachmentBoundsForTextContainer_proposedLineFragment_glyphPosition_characterIndex_(
            textContainer, lineFrag, position, charIndex
        )
        rect.origin.y = self._verticalOffset
        return rect


def make_pill_attachment(label_text: str) -> NSAttributedString:
    """Create a rounded blue pill image attachment for display only."""
    font = NSFont.systemFontOfSize_(FONT_SIZE)
    attrs = {NSFontAttributeName: font, NSForegroundColorAttributeName: NSColor.blackColor()}
    text_ns = objc.lookUpClass("NSString").stringWithString_(label_text)
    txt_size = text_ns.sizeWithAttributes_(attrs)

    padding_x = 6
    padding_y = 1
    width = txt_size.width + 2 * padding_x
    height = txt_size.height

    img = NSImage.alloc().initWithSize_((width, height))
    img.lockFocus()

    NSColor.colorWithCalibratedRed_green_blue_alpha_(0.8, 0.9, 1.0, 1.0).set()
    path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
        NSMakeRect(0, 0, width, height), 4.0, 4.0
    )
    path.fill()

    text_rect = NSMakeRect(padding_x, (height - txt_size.height) / 2, txt_size.width, txt_size.height)
    text_ns.drawInRect_withAttributes_(text_rect, attrs)
    img.unlockFocus()

    attachment = _InlineTextAttachment.alloc().init()
    attachment.setImage_(img)

    # Lower the pill to align to baseline nicely
    vertical_offset = font.descender() - padding_y
    attachment.setVerticalOffset_(vertical_offset)

    return NSAttributedString.attributedStringWithAttachment_(attachment)


def build_tag_attributed(raw_text: str, display_text: str, typing_attrs=None) -> NSAttributedString:
    """Wrap a pill attachment and store raw text under TAG_ATTR_NAME."""
    pill = make_pill_attachment(display_text).mutableCopy()
    if typing_attrs is not None:
        pill.addAttributes_range_(typing_attrs, (0, 1))
    pill.addAttribute_value_range_(TAG_ATTR_NAME, raw_text, (0, 1))
    return pill


def _collect_prefixes(plugins: Iterable[object]) -> Tuple[set[str], set[str], set[str]]:
    """Return (normal_prefixes, path_like_prefixes, prefix_only) sets.

    prefix_only includes prefixes that should NOT be treated as complete on
    equality (e.g., '@http://').
    """
    normal = set()
    path_like = set()
    prefix_only = set()
    for p in plugins or []:
        try:
            for pr in p.get_prefixes():
                normal.add(pr)
                # Heuristic: treat protocol-style prefixes as prefix-only
                if pr.endswith("://"):
                    prefix_only.add(pr)
        except Exception:
            pass
        # FileTag exposes PATH_PREFIXES; detect defensively
        try:
            for pr in getattr(p, "PATH_PREFIXES", []):
                path_like.add(pr)
        except Exception:
            pass
    return normal, path_like, prefix_only


def display_string_for_tag(raw_tag: str, plugins: Iterable[object]) -> str:
    """Return display label for raw_tag using plugin display_string.

    Only consider real expansion prefixes for the plugin. Catch-all
    autocomplete providers are ignored to avoid mislabeling.
    """
    for p in plugins or []:
        try:
            prefixes = set(p.get_prefixes())
        except Exception:
            prefixes = set()

        matched = False
        try:
            if any(raw_tag.startswith(pr) for pr in prefixes):
                matched = True
            else:
                # Special-case FileTag path-like prefixes
                for pr in getattr(p, "PATH_PREFIXES", []):
                    if raw_tag.startswith(pr):
                        matched = True
                        break
        except Exception:
            matched = False

        if matched:
            try:
                return p.display_string(raw_tag)
            except Exception:
                return raw_tag
    return raw_tag


def find_token_range(text: str, caret_index: int) -> tuple[int, int]:
    """Return start/end for token around caret; respects quotes."""
    if caret_index < 0:
        caret_index = 0
    if caret_index > len(text):
        caret_index = len(text)
    # Find start
    start = caret_index
    in_quotes = False
    while start > 0:
        ch = text[start - 1]
        if ch == '"':
            in_quotes = not in_quotes
            start -= 1
            continue
        if ch in (' ', '\n', '\t') and not in_quotes:
            break
        start -= 1
    # Find end
    end = caret_index
    in_quotes = False
    while end < len(text):
        ch = text[end]
        if ch == '"':
            in_quotes = not in_quotes
            end += 1
            continue
        if ch in (' ', '\n', '\t') and not in_quotes:
            break
        end += 1
    return start, end


def render_text_with_pills(text: str, color, font, shortcuts: Iterable[str], plugins: Iterable[object]) -> NSAttributedString:
    """Return attributed string with recognized tokens replaced by pills.

    Only visual; it does not store TAG_ATTR_NAME (history is read-only).
    """
    result = NSMutableAttributedString.alloc().init()
    attrs = {NSForegroundColorAttributeName: color, NSFontAttributeName: font}

    normal_prefixes, path_like, _prefix_only = _collect_prefixes(plugins)
    shortcuts_set = set(shortcuts or [])

    i = 0
    while i < len(text):
        # Skip spaces/newlines quickly
        if text[i] in (' ', '\n', '\t'):
            result.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(text[i], attrs))
            i += 1
            continue

        # Extract token
        start, end = find_token_range(text, i)
        token = text[start:end]
        i = end

        # Shortcut pill
        if token in shortcuts_set:
            disp = token
            result.appendAttributedString_(make_pill_attachment(disp))
            continue

        # Plugin slash-command pill
        if token.startswith('/') and token in normal_prefixes:
            result.appendAttributedString_(make_pill_attachment(token))
            continue

        # Tag pill check
        if token.startswith('@'):
            # Fast path for prefixes or path-like
            if any(token.startswith(p) for p in normal_prefixes) or any(token.startswith(p) for p in path_like):
                disp = display_string_for_tag(token, plugins)
                result.appendAttributedString_(make_pill_attachment(disp))
                continue

        # Fallback: plain text
        result.appendAttributedString_(NSAttributedString.alloc().initWithString_attributes_(token, attrs))

    return result


def build_input_attributed_with_caret(
    text: str,
    typing_attrs,
    shortcuts: Iterable[str],
    plugins: Iterable[object],
    caret_plain_index: int,
):
    """Build full-buffer attributed string for input with pills and map caret.

    Returns (NSAttributedString, caret_attr_index). Plain index counts raw
    characters including tag raw text; attachments count as length of their
    underlying raw tag in plain space.
    """
    result = NSMutableAttributedString.alloc().init()
    shortcuts_set = set(shortcuts or [])

    # Clean typing attributes
    base_attrs = typing_attrs.mutableCopy() if typing_attrs is not None else None
    if base_attrs is not None and base_attrs.objectForKey_(TAG_ATTR_NAME):
        base_attrs.removeObjectForKey_(TAG_ATTR_NAME)

    def append_plain(s: str):
        if not s:
            return
        # Ensure plain text uses basic readable attributes when typing_attrs is None
        if base_attrs is None:
            plain_font = NSFont.systemFontOfSize_(FONT_SIZE)
            attr = NSAttributedString.alloc().initWithString_attributes_(
                s, {NSFontAttributeName: plain_font, NSForegroundColorAttributeName: NSColor.blackColor()}
            )
        else:
            attr = NSAttributedString.alloc().initWithString_attributes_(s, base_attrs)
        result.appendAttributedString_(attr)

    def is_delim(ch: str) -> bool:
        return ch in (' ', '\n', '\t')

    # Precompute plugin prefix sets
    normal_prefixes, path_prefixes, prefix_only = _collect_prefixes(plugins)

    def token_is_url_tag(tok: str) -> bool:
        # Match @http(s):// and require valid scheme+netloc
        if not (tok.startswith('@http://') or tok.startswith('@https://')):
            return False
        url = tok[1:]
        parsed = urlparse(url)
        return bool(parsed.scheme and parsed.netloc)

    plain_index = 0
    caret_attr_index = 0
    caret_set = False
    i = 0
    while i < len(text):
        ch = text[i]
        if is_delim(ch):
            before_len = result.length()
            append_plain(ch)
            i += 1
            plain_index += 1
            if not caret_set and caret_plain_index == plain_index:
                # Caret sits after this delimiter
                caret_attr_index = before_len + 1
                caret_set = True
            continue

        # Token start
        start_i = i
        token = None
        # Quoted path token: @"..."
        if text.startswith('@"', i):
            i += 2
            while i < len(text) and text[i] != '"':
                i += 1
            if i < len(text) and text[i] == '"':
                i += 1  # include closing quote
            token = text[start_i:i]
        else:
            # Read until next delimiter
            while i < len(text) and not is_delim(text[i]):
                i += 1
            token = text[start_i:i]

        # Decide pill type
        made_pill = False
        raw = None
        display = None
        # Determine next delimiter char (None when at EOL)
        next_delim = text[i] if i < len(text) else None

        # Shortcuts convert only when followed by whitespace (not at EOL)
        if token in shortcuts_set and next_delim in (' ', '\n', '\t'):
            raw = token
            display = token
        elif token.startswith('/') and token in normal_prefixes and next_delim in (' ', '\n', '\t'):
            raw = token
            display = token
        elif token.startswith('@'):
            # Simple exact-match tags require trailing whitespace and must not be prefix-only
            if token in normal_prefixes and token not in prefix_only and next_delim in (' ', '\n', '\t'):
                raw = token
                display = display_string_for_tag(token, plugins)
            # URL-like tags convert only when followed by whitespace and look valid
            elif token_is_url_tag(token) and next_delim in (' ', '\n', '\t'):
                raw = token
                display = display_string_for_tag(token, plugins)
            # Path-like: quoted tokens were already captured; accept unquoted @/ or @~ tokens as-is
            elif any(token.startswith(p) for p in path_prefixes) and next_delim in (' ', '\n', '\t'):
                # If quoted variant, ensure it ended with quote (handled by tokenizer)
                raw = token
                display = display_string_for_tag(token, plugins)

        if raw is not None and display is not None:
            attr = build_tag_attributed(raw, display, base_attrs)
            before_len = result.length()
            token_plain_len = len(token)
            # Caret mapping: if caret falls inside this plain token, place after pill
            if not caret_set and (plain_index <= caret_plain_index <= plain_index + token_plain_len):
                caret_attr_index = before_len + 1
                caret_set = True
            result.appendAttributedString_(attr)
            plain_index += token_plain_len
            made_pill = True

        if not made_pill:
            before_len = result.length()
            token_plain_len = len(token)
            append_plain(token)
            if not caret_set and (plain_index <= caret_plain_index <= plain_index + token_plain_len):
                caret_attr_index = before_len + (caret_plain_index - plain_index)
                caret_set = True
            plain_index += token_plain_len

    # Clamp caret
    if not caret_set:
        caret_attr_index = result.length()
    if caret_attr_index > result.length():
        caret_attr_index = result.length()
    return result, caret_attr_index


