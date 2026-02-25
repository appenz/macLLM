import re

from Cocoa import (
    NSAttributedString, NSForegroundColorAttributeName, NSFontAttributeName,
    NSUnderlineStyleAttributeName, NSUnderlineStyleSingle, NSUnderlinePatternDot,
    NSUnderlineColorAttributeName, NSColor,
)
from AppKit import NSLinkAttributeName
from Foundation import NSMutableAttributedString, NSURL

_UNDERLINE_STYLE = NSUnderlineStyleSingle | NSUnderlinePatternDot
_LINK_COLOR = NSColor.colorWithCalibratedWhite_alpha_(0.50, 1.0)
_UNDERLINE_COLOR = NSColor.colorWithCalibratedWhite_alpha_(0.50, 0.45)

_URL_RE = re.compile(r'https?://\S+')
_LINK_ARROW = " \u2197"

_TRAILING_PUNCT = frozenset('.,;:!?\'")}]>')


def _clean_url(raw):
    """Strip trailing punctuation that is likely part of the surrounding sentence."""
    url = raw
    while url and url[-1] in _TRAILING_PUNCT:
        if url[-1] == ')' and url.count('(') >= url.count(')'):
            break
        url = url[:-1]
    return url


def linkify_text(text, color, font):
    """Return an NSAttributedString with bare https?:// URLs rendered as clickable links."""
    result = NSMutableAttributedString.alloc().init()
    plain_attrs = {
        NSForegroundColorAttributeName: color,
        NSFontAttributeName: font,
    }

    last_end = 0
    for m in _URL_RE.finditer(text):
        url = _clean_url(m.group())
        url_end = m.start() + len(url)

        if m.start() > last_end:
            plain = NSAttributedString.alloc().initWithString_attributes_(
                text[last_end:m.start()], plain_attrs)
            result.appendAttributedString_(plain)

        link_url = NSURL.URLWithString_(url)
        url_attrs = {
            NSForegroundColorAttributeName: _LINK_COLOR,
            NSFontAttributeName: font,
            NSLinkAttributeName: link_url,
            NSUnderlineStyleAttributeName: _UNDERLINE_STYLE,
            NSUnderlineColorAttributeName: _UNDERLINE_COLOR,
        }
        url_str = NSAttributedString.alloc().initWithString_attributes_(url, url_attrs)
        result.appendAttributedString_(url_str)
        arrow_attrs = {
            NSForegroundColorAttributeName: _LINK_COLOR,
            NSFontAttributeName: font,
            NSLinkAttributeName: link_url,
        }
        arrow_str = NSAttributedString.alloc().initWithString_attributes_(_LINK_ARROW, arrow_attrs)
        result.appendAttributedString_(arrow_str)
        last_end = url_end

    if last_end < len(text):
        tail = NSAttributedString.alloc().initWithString_attributes_(
            text[last_end:], plain_attrs)
        result.appendAttributedString_(tail)

    return result


def render_link_span(children, start, href, color, font):
    """Render children between link_open and link_close with a link attribute.

    Returns the NSAttributedString for the link span.  The caller is
    responsible for advancing the child index past link_close.
    """
    from macllm.markdown.inline import _append_str

    result = NSMutableAttributedString.alloc().init()
    i = start
    while i < len(children):
        child = children[i]
        if child.type == 'link_close':
            break
        _append_str(result, child.content or "", _LINK_COLOR, font)
        i += 1

    if result.length() > 0:
        link_url = NSURL.URLWithString_(href)
        text_len = result.length()
        result.addAttribute_value_range_(NSLinkAttributeName, link_url, (0, text_len))
        result.addAttribute_value_range_(
            NSUnderlineStyleAttributeName, _UNDERLINE_STYLE, (0, text_len))
        result.addAttribute_value_range_(
            NSUnderlineColorAttributeName, _UNDERLINE_COLOR, (0, text_len))
        arrow = NSAttributedString.alloc().initWithString_attributes_(
            _LINK_ARROW, {
                NSForegroundColorAttributeName: _LINK_COLOR,
                NSFontAttributeName: font,
                NSLinkAttributeName: link_url,
            })
        result.appendAttributedString_(arrow)

    return result, i
