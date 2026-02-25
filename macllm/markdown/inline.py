from Cocoa import NSFont, NSAttributedString, NSForegroundColorAttributeName, NSFontAttributeName
from Foundation import NSMutableAttributedString

from macllm.markdown.link import linkify_text, render_link_span


def render_inline(token, color, font):
    """Render an inline token and its children to NSAttributedString.

    Handles: text, strong (bold), softbreak, code_inline, links.
    Unknown child types are rendered as plain text via their content field.
    """
    if not token.children:
        return linkify_text(token.content or "", color, font)

    result = NSMutableAttributedString.alloc().init()
    bold_font = NSFont.boldSystemFontOfSize_(font.pointSize())
    bold = False
    children = token.children
    i = 0

    while i < len(children):
        child = children[i]

        if child.type == 'strong_open':
            bold = True
            i += 1
            continue
        if child.type == 'strong_close':
            bold = False
            i += 1
            continue

        if child.type == 'softbreak':
            _append_str(result, "\n", color, font)
            i += 1
            continue

        if child.type == 'code_inline':
            mono = NSFont.monospacedSystemFontOfSize_weight_(font.pointSize(), 0.0)
            _append_str(result, child.content, color, mono)
            i += 1
            continue

        if child.type == 'link_open':
            href = child.attrs.get('href', '') if child.attrs else ''
            link_str, i = render_link_span(children, i + 1, href, color, font)
            result.appendAttributedString_(link_str)
            i += 1  # skip link_close
            continue

        # 'text' and any unrecognised inline type — linkify bare URLs
        current_font = bold_font if bold else font
        result.appendAttributedString_(
            linkify_text(child.content or "", color, current_font))
        i += 1

    return result


def _append_str(result, text, color, font):
    attr = NSAttributedString.alloc().initWithString_attributes_(
        text, {
            NSForegroundColorAttributeName: color,
            NSFontAttributeName: font,
        }
    )
    result.appendAttributedString_(attr)
