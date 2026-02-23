from Cocoa import (
    NSFont, NSAttributedString,
    NSForegroundColorAttributeName, NSFontAttributeName,
    NSParagraphStyleAttributeName,
)
from Foundation import NSMutableAttributedString, NSMutableParagraphStyle

from macllm.markdown.inline import render_inline

FONT_SIZE = 13.0
INDENT_PER_LEVEL = 16.0
BULLET_TEXT_OFFSET = 12.0


def render_heading(tokens, start_idx, color):
    """Render a heading block.  Returns (NSAttributedString, next_index)."""
    bold_font = NSFont.boldSystemFontOfSize_(FONT_SIZE)
    result = NSMutableAttributedString.alloc().init()

    i = start_idx + 1
    while i < len(tokens) and tokens[i].type != 'heading_close':
        if tokens[i].type == 'inline':
            result.appendAttributedString_(render_inline(tokens[i], color, bold_font))
        i += 1
    return result, i + 1


def render_paragraph(tokens, start_idx, color):
    """Render a paragraph block.  Returns (NSAttributedString, next_index)."""
    font = NSFont.systemFontOfSize_(FONT_SIZE)
    result = NSMutableAttributedString.alloc().init()

    i = start_idx + 1
    while i < len(tokens) and tokens[i].type != 'paragraph_close':
        if tokens[i].type == 'inline':
            result.appendAttributedString_(render_inline(tokens[i], color, font))
        i += 1
    return result, i + 1


def render_list(tokens, start_idx, color, depth=0):
    """Render a bullet or ordered list with hanging-indent for wrapped lines.

    Returns (NSAttributedString, next_index).
    """
    font = NSFont.systemFontOfSize_(FONT_SIZE)
    result = NSMutableAttributedString.alloc().init()

    is_ordered = tokens[start_idx].type == 'ordered_list_open'
    close_type = 'ordered_list_close' if is_ordered else 'bullet_list_close'

    indent = depth * INDENT_PER_LEVEL
    style = NSMutableParagraphStyle.alloc().init()
    style.setFirstLineHeadIndent_(indent)
    style.setHeadIndent_(indent + BULLET_TEXT_OFFSET)

    i = start_idx + 1
    item_number = 0
    first_item = True

    while i < len(tokens) and tokens[i].type != close_type:
        if tokens[i].type == 'list_item_open':
            item_number += 1
            i += 1

            if not first_item:
                nl = NSAttributedString.alloc().initWithString_("\n")
                result.appendAttributedString_(nl)
            first_item = False

            item_line = NSMutableAttributedString.alloc().init()

            prefix = f"{item_number}. " if is_ordered else "\u2022 "
            prefix_attr = NSAttributedString.alloc().initWithString_attributes_(
                prefix, {
                    NSForegroundColorAttributeName: color,
                    NSFontAttributeName: font,
                }
            )
            item_line.appendAttributedString_(prefix_attr)

            nested_parts = NSMutableAttributedString.alloc().init()

            while i < len(tokens) and tokens[i].type != 'list_item_close':
                if tokens[i].type == 'paragraph_open':
                    i += 1
                    while i < len(tokens) and tokens[i].type != 'paragraph_close':
                        if tokens[i].type == 'inline':
                            item_line.appendAttributedString_(
                                render_inline(tokens[i], color, font)
                            )
                        i += 1
                    i += 1  # skip paragraph_close
                elif tokens[i].type in ('bullet_list_open', 'ordered_list_open'):
                    nested_attr, i = render_list(tokens, i, color, depth + 1)
                    nl = NSAttributedString.alloc().initWithString_("\n")
                    nested_parts.appendAttributedString_(nl)
                    nested_parts.appendAttributedString_(nested_attr)
                else:
                    i += 1

            i += 1  # skip list_item_close

            # Apply hanging-indent style to the item text (but not nested lists,
            # which carry their own deeper indent).
            item_line.addAttribute_value_range_(
                NSParagraphStyleAttributeName, style,
                (0, item_line.length()),
            )
            result.appendAttributedString_(item_line)

            if nested_parts.length() > 0:
                result.appendAttributedString_(nested_parts)
        else:
            i += 1

    return result, i + 1


def render_fence(tokens, start_idx, color):
    """Render a fenced / indented code block as monospaced text."""
    token = tokens[start_idx]
    mono_font = NSFont.monospacedSystemFontOfSize_weight_(FONT_SIZE, 0.0)

    content = (token.content or "").rstrip('\n')
    attr = NSMutableAttributedString.alloc().initWithString_attributes_(
        content, {
            NSForegroundColorAttributeName: color,
            NSFontAttributeName: mono_font,
        }
    )
    return attr, start_idx + 1
