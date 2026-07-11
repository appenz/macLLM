"""Markdown layout tests for conversation rendering."""

from Cocoa import NSColor, NSParagraphStyleAttributeName
from Foundation import NSString

from macllm.markdown import render_markdown
from macllm.markdown.blocks import LIST_ITEM_SPACING, LIST_SPACING_BEFORE


def _paragraph_styles(attr_str):
    text = str(attr_str.string())
    ns_text = NSString.stringWithString_(text)
    styles = []
    pos = 0
    while pos < attr_str.length():
        para_range = ns_text.paragraphRangeForRange_((pos, 0))
        style, _ = attr_str.attribute_atIndex_effectiveRange_(
            NSParagraphStyleAttributeName,
            para_range.location,
            None,
        )
        styles.append(style)
        pos = para_range.location + para_range.length
    return styles


def test_list_has_symmetric_boundary_spacing():
    """First and last list items should have equal outer spacing."""
    color = NSColor.darkGrayColor()
    markdown = (
        "Intro paragraph.\n\n"
        "- first item\n"
        "- second item\n"
        "- third item\n\n"
        "After paragraph."
    )
    rendered = render_markdown(markdown, color)
    styles = _paragraph_styles(rendered)

    list_styles = [
        style for style in styles
        if style is not None and style.paragraphSpacingBefore() > 0
    ]
    trailing_list_styles = [
        style for style in styles
        if style is not None and style.paragraphSpacing() >= LIST_SPACING_BEFORE
    ]

    assert list_styles, "expected a list item with leading spacing"
    assert trailing_list_styles, "expected a list item with trailing spacing"
    assert list_styles[0].paragraphSpacingBefore() == LIST_SPACING_BEFORE
    assert trailing_list_styles[-1].paragraphSpacing() == LIST_SPACING_BEFORE


def test_list_items_keep_compact_internal_spacing():
    """Middle list items should stay compact between bullets."""
    color = NSColor.darkGrayColor()
    markdown = "- one\n- two\n- three"
    rendered = render_markdown(markdown, color)
    styles = [style for style in _paragraph_styles(rendered) if style is not None]

    assert len(styles) == 3
    assert styles[0].paragraphSpacing() == LIST_ITEM_SPACING
    assert styles[1].paragraphSpacing() == LIST_ITEM_SPACING
    assert styles[2].paragraphSpacing() == LIST_SPACING_BEFORE
