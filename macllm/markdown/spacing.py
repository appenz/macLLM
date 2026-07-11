"""Unified inter-block spacing for markdown rendering.

All vertical gaps between blocks are chosen from this table so margins
never stack (e.g. paragraph trailing + list leading).
"""

FONT_SIZE = 14.0

PARAGRAPH_GAP = FONT_SIZE * 0.75
BLOCK_GAP = FONT_SIZE * 0.25
HEAVY_GAP = PARAGRAPH_GAP

_BLOCK_KIND = {
    "paragraph_open": "paragraph",
    "heading_open": "heading",
    "bullet_list_open": "list",
    "ordered_list_open": "list",
    "table_open": "heavy",
    "fence": "heavy",
    "code_block": "heavy",
    "blockquote_open": "heavy",
}

# spacingBefore applied to the incoming block; one value per transition.
_GAP_BEFORE = {
    ("start", "paragraph"): 0.0,
    ("start", "heading"): 0.0,
    ("start", "list"): 0.0,
    ("start", "heavy"): 0.0,
    ("paragraph", "paragraph"): PARAGRAPH_GAP,
    ("paragraph", "heading"): PARAGRAPH_GAP,
    ("paragraph", "list"): BLOCK_GAP,
    ("paragraph", "heavy"): HEAVY_GAP,
    ("heading", "paragraph"): BLOCK_GAP,
    ("heading", "heading"): BLOCK_GAP,
    ("heading", "list"): BLOCK_GAP,
    ("heading", "heavy"): HEAVY_GAP,
    ("list", "paragraph"): BLOCK_GAP,
    ("list", "heading"): PARAGRAPH_GAP,
    ("list", "list"): BLOCK_GAP,
    ("list", "heavy"): HEAVY_GAP,
    ("heavy", "paragraph"): HEAVY_GAP,
    ("heavy", "heading"): HEAVY_GAP,
    ("heavy", "list"): HEAVY_GAP,
    ("heavy", "heavy"): HEAVY_GAP,
}


def block_kind(token_type: str) -> str:
    return _BLOCK_KIND.get(token_type, "paragraph")


def gap_before(prev_type: str | None, current_type: str) -> float:
    prev = "start" if prev_type is None else block_kind(prev_type)
    current = block_kind(current_type)
    return _GAP_BEFORE.get((prev, current), BLOCK_GAP)


def gap_after(current_type: str, next_type: str | None) -> float:
    if next_type is None:
        return 0.0
    return gap_before(current_type, next_type)
