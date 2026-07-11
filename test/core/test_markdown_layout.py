"""Markdown layout tests for conversation rendering."""

from Cocoa import NSColor, NSParagraphStyleAttributeName, NSFontAttributeName
from Foundation import NSString

from macllm.markdown import render_markdown
from macllm.markdown.blocks import (
    DEFAULT_HEADING_FONT_SIZE,
    HEADING_FONT_SIZES,
    LINE_HEIGHT,
    LIST_ITEM_SPACING,
    apply_block_margins,
)
from macllm.markdown.spacing import BLOCK_GAP, PARAGRAPH_GAP, gap_before


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


def _style_before(text, marker):
    rendered = render_markdown(text, NSColor.darkGrayColor())
    idx = str(rendered.string()).index(marker)
    style, _ = rendered.attribute_atIndex_effectiveRange_(
        NSParagraphStyleAttributeName, idx, None,
    )
    return style.paragraphSpacingBefore() if style is not None else 0.0


def _style_after(text, marker):
    rendered = render_markdown(text, NSColor.darkGrayColor())
    idx = str(rendered.string()).index(marker)
    style, _ = rendered.attribute_atIndex_effectiveRange_(
        NSParagraphStyleAttributeName, idx, None,
    )
    return style.paragraphSpacing() if style is not None else 0.0


def test_list_items_keep_compact_internal_spacing():
    """Middle list items should stay compact between bullets."""
    color = NSColor.darkGrayColor()
    rendered = render_markdown("- one\n- two\n- three", color)
    styles = [style for style in _paragraph_styles(rendered) if style is not None]

    assert len(styles) == 3
    assert styles[0].paragraphSpacing() == LIST_ITEM_SPACING
    assert styles[1].paragraphSpacing() == LIST_ITEM_SPACING
    assert styles[2].paragraphSpacing() == 0.0


def test_paragraphs_use_prose_line_height():
    color = NSColor.darkGrayColor()
    rendered = render_markdown("First paragraph.\n\nSecond paragraph.", color)
    styles = [style for style in _paragraph_styles(rendered) if style is not None]

    assert len(styles) == 2
    for style in styles:
        assert style.minimumLineHeight() == LINE_HEIGHT
        assert style.maximumLineHeight() == LINE_HEIGHT


def test_headings_use_size_hierarchy():
    rendered = render_markdown("# Title\n\n## Section\n\n### Subsection", NSColor.darkGrayColor())
    text = str(rendered.string())

    title_font, _ = rendered.attribute_atIndex_effectiveRange_(
        NSFontAttributeName, text.index("Title"), None,
    )
    section_font, _ = rendered.attribute_atIndex_effectiveRange_(
        NSFontAttributeName, text.index("Section"), None,
    )
    subsection_font, _ = rendered.attribute_atIndex_effectiveRange_(
        NSFontAttributeName, text.index("Subsection"), None,
    )

    assert title_font.pointSize() == HEADING_FONT_SIZES[1]
    assert section_font.pointSize() == HEADING_FONT_SIZES[2]
    assert subsection_font.pointSize() == DEFAULT_HEADING_FONT_SIZE


def test_list_gap_is_consistent_after_paragraph_and_heading():
    """Lists should get the same leading gap regardless of predecessor."""
    para_gap = _style_before("Intro text.\n\n- item one", "item one")
    heading_gap = _style_before("## Climate highlights\n\n- item one", "item one")

    assert para_gap == BLOCK_GAP
    assert heading_gap == BLOCK_GAP
    assert para_gap == heading_gap


def test_heading_to_paragraph_gap_matches_list_gap():
    after_heading = _style_before("## Modern city\n\nBody text follows.", "Body text")
    assert after_heading == BLOCK_GAP


def test_paragraph_to_paragraph_gap_is_larger_than_list_gap():
    gap = _style_before("First paragraph.\n\nSecond paragraph.", "Second")
    assert gap == PARAGRAPH_GAP
    assert PARAGRAPH_GAP > BLOCK_GAP


def test_list_has_symmetric_outer_spacing():
    before = _style_before("Intro.\n\n- one\n- two\n\nAfter.", "one")
    after = _style_after("Intro.\n\n- one\n- two\n\nAfter.", "two")
    assert before == BLOCK_GAP
    assert after == BLOCK_GAP


def test_apply_block_margins_updates_first_and_last_paragraph():
    from Foundation import NSMutableAttributedString

    attr = NSMutableAttributedString.alloc().initWithString_("one\n- two\n- three")
    apply_block_margins(attr, spacing_before=4.0, spacing_after=6.0)
    styles = [s for s in _paragraph_styles(attr) if s is not None]

    assert styles[0].paragraphSpacingBefore() == 4.0
    assert styles[0].paragraphSpacing() == 0.0
    assert styles[-1].paragraphSpacing() == 6.0


def test_gap_before_table():
    assert gap_before("paragraph_open", "table_open") == PARAGRAPH_GAP
