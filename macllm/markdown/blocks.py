from Cocoa import (
    NSFont, NSAttributedString,
    NSForegroundColorAttributeName, NSFontAttributeName,
    NSParagraphStyleAttributeName, NSLinkAttributeName,
)
from AppKit import NSTextTab
from Foundation import NSMutableAttributedString, NSMutableParagraphStyle

from macllm.markdown.inline import render_inline

FONT_SIZE = 13.0
CODE_BLOCK_FONT_SIZE = 11.5
CODE_BLOCK_LEFT_INDENT = 8.0
COLLAPSE_PREVIEW_LINES = 5
COLLAPSE_THRESHOLD_LINES = 10

LIST_BASE_INDENT = 14.0
INDENT_PER_LEVEL = 16.0
BULLET_TEXT_OFFSET = 14.0
LIST_SPACING_BEFORE = 6.0
LIST_ITEM_SPACING = 2.0


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


def _make_list_item_style(indent, is_first):
    """Build an NSMutableParagraphStyle for one list item.

    Uses a tab stop so bullet/number text always starts at a fixed column,
    and adds vertical breathing room before the first item.
    """
    content_col = indent + BULLET_TEXT_OFFSET
    style = NSMutableParagraphStyle.alloc().init()
    style.setFirstLineHeadIndent_(indent)
    style.setHeadIndent_(content_col)
    style.setTabStops_([])
    tab = NSTextTab.alloc().initWithTextAlignment_location_options_(
        0, content_col, {},
    )
    style.setTabStops_([tab])
    style.setDefaultTabInterval_(BULLET_TEXT_OFFSET)
    if is_first:
        style.setParagraphSpacingBefore_(LIST_SPACING_BEFORE)
    style.setParagraphSpacing_(LIST_ITEM_SPACING)
    return style


def render_list(tokens, start_idx, color, depth=0):
    """Render a bullet or ordered list with hanging-indent for wrapped lines.

    Returns (NSAttributedString, next_index).
    """
    font = NSFont.systemFontOfSize_(FONT_SIZE)
    result = NSMutableAttributedString.alloc().init()

    is_ordered = tokens[start_idx].type == 'ordered_list_open'
    close_type = 'ordered_list_close' if is_ordered else 'bullet_list_close'

    indent = LIST_BASE_INDENT + depth * INDENT_PER_LEVEL

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

            style = _make_list_item_style(indent, first_item)
            first_item = False

            item_line = NSMutableAttributedString.alloc().init()

            prefix = f"{item_number}.\t" if is_ordered else "\u2022\t"
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
    """Render a fenced/indented code block with smaller font, copy link, and collapse."""
    from macllm.markdown import register_code_block, is_code_block_expanded

    token = tokens[start_idx]
    mono_font = NSFont.monospacedSystemFontOfSize_weight_(CODE_BLOCK_FONT_SIZE, 0.0)

    content = (token.content or "").rstrip('\n')
    block_id = register_code_block(content)
    lines = content.split('\n')

    result = NSMutableAttributedString.alloc().init()

    needs_collapse = len(lines) > COLLAPSE_THRESHOLD_LINES
    expanded = is_code_block_expanded(block_id)

    if needs_collapse and not expanded:
        display_content = '\n'.join(lines[:COLLAPSE_PREVIEW_LINES])
    else:
        display_content = content

    code_attr = NSAttributedString.alloc().initWithString_attributes_(
        display_content, {
            NSForegroundColorAttributeName: color,
            NSFontAttributeName: mono_font,
        }
    )
    result.appendAttributedString_(code_attr)

    muted = color.colorWithAlphaComponent_(0.40)
    link_font = NSFont.systemFontOfSize_(10.0)

    if needs_collapse:
        if not expanded:
            remaining = len(lines) - COLLAPSE_PREVIEW_LINES
            toggle_text = f"\n  \u25b8 {remaining} more lines"
        else:
            toggle_text = "\n  \u25be collapse"

        toggle_attr = NSAttributedString.alloc().initWithString_attributes_(
            toggle_text, {
                NSForegroundColorAttributeName: muted,
                NSFontAttributeName: link_font,
                NSLinkAttributeName: f"macllm://toggle-code/{block_id}",
            }
        )
        result.appendAttributedString_(toggle_attr)

    copy_prefix = "  " if needs_collapse else "\n  "
    copy_attr = NSAttributedString.alloc().initWithString_attributes_(
        f"{copy_prefix}[copy]", {
            NSForegroundColorAttributeName: muted,
            NSFontAttributeName: link_font,
            NSLinkAttributeName: f"macllm://copy-code/{block_id}",
        }
    )
    result.appendAttributedString_(copy_attr)

    style = NSMutableParagraphStyle.alloc().init()
    style.setFirstLineHeadIndent_(CODE_BLOCK_LEFT_INDENT)
    style.setHeadIndent_(CODE_BLOCK_LEFT_INDENT)
    result.addAttribute_value_range_(
        NSParagraphStyleAttributeName, style, (0, result.length()),
    )

    return result, start_idx + 1, block_id


def render_blockquote(tokens, start_idx, color):
    """Render a blockquote with smaller font, copy link, and collapse."""
    from macllm.markdown import register_code_block, is_code_block_expanded

    parts = []
    i = start_idx + 1
    while i < len(tokens) and tokens[i].type != 'blockquote_close':
        if tokens[i].type == 'inline':
            parts.append(tokens[i].content or "")
        i += 1

    content = '\n'.join(parts).strip()
    if not content:
        return NSMutableAttributedString.alloc().init(), i + 1, None

    block_id = register_code_block(content)
    lines = content.split('\n')
    font = NSFont.systemFontOfSize_(CODE_BLOCK_FONT_SIZE)

    result = NSMutableAttributedString.alloc().init()

    needs_collapse = len(lines) > COLLAPSE_THRESHOLD_LINES
    expanded = is_code_block_expanded(block_id)

    if needs_collapse and not expanded:
        display_content = '\n'.join(lines[:COLLAPSE_PREVIEW_LINES])
    else:
        display_content = content

    text_attr = NSAttributedString.alloc().initWithString_attributes_(
        display_content, {
            NSForegroundColorAttributeName: color.colorWithAlphaComponent_(0.75),
            NSFontAttributeName: font,
        }
    )
    result.appendAttributedString_(text_attr)

    muted = color.colorWithAlphaComponent_(0.40)
    link_font = NSFont.systemFontOfSize_(10.0)

    if needs_collapse:
        if not expanded:
            remaining = len(lines) - COLLAPSE_PREVIEW_LINES
            toggle_text = f"\n  \u25b8 {remaining} more lines"
        else:
            toggle_text = "\n  \u25be collapse"

        toggle_attr = NSAttributedString.alloc().initWithString_attributes_(
            toggle_text, {
                NSForegroundColorAttributeName: muted,
                NSFontAttributeName: link_font,
                NSLinkAttributeName: f"macllm://toggle-code/{block_id}",
            }
        )
        result.appendAttributedString_(toggle_attr)

    copy_prefix = "  " if needs_collapse else "\n  "
    copy_attr = NSAttributedString.alloc().initWithString_attributes_(
        f"{copy_prefix}[copy]", {
            NSForegroundColorAttributeName: muted,
            NSFontAttributeName: link_font,
            NSLinkAttributeName: f"macllm://copy-code/{block_id}",
        }
    )
    result.appendAttributedString_(copy_attr)

    style = NSMutableParagraphStyle.alloc().init()
    style.setFirstLineHeadIndent_(CODE_BLOCK_LEFT_INDENT)
    style.setHeadIndent_(CODE_BLOCK_LEFT_INDENT)
    result.addAttribute_value_range_(
        NSParagraphStyleAttributeName, style, (0, result.length()),
    )

    return result, i + 1, block_id
