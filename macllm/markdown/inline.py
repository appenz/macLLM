from Cocoa import NSFont, NSAttributedString, NSForegroundColorAttributeName, NSFontAttributeName
from Foundation import NSMutableAttributedString


def render_inline(token, color, font):
    """Render an inline token and its children to NSAttributedString.

    Handles: text, strong (bold), softbreak, code_inline.
    Unknown child types are rendered as plain text via their content field.
    """
    if not token.children:
        attributes = {
            NSForegroundColorAttributeName: color,
            NSFontAttributeName: font,
        }
        return NSMutableAttributedString.alloc().initWithString_attributes_(
            token.content or "", attributes
        )

    result = NSMutableAttributedString.alloc().init()
    bold_font = NSFont.boldSystemFontOfSize_(font.pointSize())
    bold = False

    for child in token.children:
        if child.type == 'strong_open':
            bold = True
            continue
        if child.type == 'strong_close':
            bold = False
            continue

        if child.type == 'softbreak':
            _append_str(result, "\n", color, font)
            continue

        if child.type == 'code_inline':
            mono = NSFont.monospacedSystemFontOfSize_weight_(font.pointSize(), 0.0)
            _append_str(result, child.content, color, mono)
            continue

        # 'text' and any unrecognised inline type — render content as-is
        current_font = bold_font if bold else font
        _append_str(result, child.content or "", color, current_font)

    return result


def _append_str(result, text, color, font):
    attr = NSAttributedString.alloc().initWithString_attributes_(
        text, {
            NSForegroundColorAttributeName: color,
            NSFontAttributeName: font,
        }
    )
    result.appendAttributedString_(attr)
