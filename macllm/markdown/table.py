import re

from Cocoa import (
    NSFont, NSAttributedString,
    NSForegroundColorAttributeName, NSFontAttributeName,
    NSParagraphStyleAttributeName,
)
from AppKit import NSLineBreakByTruncatingTail
from Foundation import NSMutableAttributedString, NSMutableParagraphStyle

TABLE_FONT_SIZE = 11.5
TABLE_LEFT_INDENT = 8.0
COL_GAP = "  "

_NUMERIC_RE = re.compile(r'^[-+]?[$€£¥]?\d[\d,. ]*[%$€£¥]?$')


def render_table(tokens, start_idx, color):
    """Render a markdown table as monospaced, column-aligned text.

    - Header row in bold monospace, data rows slightly muted.
    - Numeric columns are right-aligned.
    - Overflow is visually truncated (NSLineBreakByTruncatingTail) so copy
      still captures the full table content.
    Returns (NSAttributedString, next_index).
    """
    headers, rows, end_idx = _collect_cells(tokens, start_idx)

    all_rows = ([headers] if headers else []) + rows
    if not all_rows:
        return NSMutableAttributedString.alloc().init(), end_idx

    num_cols = max(len(r) for r in all_rows)
    col_widths = [0] * num_cols
    for row in all_rows:
        for j, cell in enumerate(row):
            col_widths[j] = max(col_widths[j], len(cell))

    alignments = _detect_alignments(rows, num_cols)

    mono = NSFont.monospacedSystemFontOfSize_weight_(TABLE_FONT_SIZE, 0.0)
    bold_mono = NSFont.monospacedSystemFontOfSize_weight_(TABLE_FONT_SIZE, 0.4)

    data_color = color.colorWithAlphaComponent_(0.75)
    sep_color = color.colorWithAlphaComponent_(0.30)

    result = NSMutableAttributedString.alloc().init()

    if headers:
        _append(result, _format_row(headers, col_widths, num_cols, alignments), color, bold_mono)
        sep_text = "\n" + COL_GAP.join("\u2500" * w for w in col_widths)
        _append(result, sep_text, sep_color, mono)

    for row in rows:
        _append(result, "\n" + _format_row(row, col_widths, num_cols, alignments), data_color, mono)

    # Apply paragraph style for left indent and tail-truncation on overflow.
    # The underlying string stays intact so copy/paste gets the full table.
    style = NSMutableParagraphStyle.alloc().init()
    style.setFirstLineHeadIndent_(TABLE_LEFT_INDENT)
    style.setHeadIndent_(TABLE_LEFT_INDENT)
    style.setLineBreakMode_(NSLineBreakByTruncatingTail)

    result.addAttribute_value_range_(
        NSParagraphStyleAttributeName, style,
        (0, result.length()),
    )

    return result, end_idx


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _collect_cells(tokens, start_idx):
    """Walk table tokens and return (headers, rows, next_index).

    Cell text is extracted as plain text (markdown formatting stripped).
    """
    headers = []
    rows = []
    current_row = []
    in_header = False

    i = start_idx + 1
    while i < len(tokens) and tokens[i].type != 'table_close':
        t = tokens[i]
        if t.type == 'thead_open':
            in_header = True
        elif t.type == 'thead_close':
            in_header = False
        elif t.type == 'tr_open':
            current_row = []
        elif t.type == 'tr_close':
            if in_header:
                headers = current_row
            else:
                rows.append(current_row)
        elif t.type == 'inline':
            current_row.append(_plain_text(t))
        i += 1

    return headers, rows, i + 1


def _plain_text(token):
    """Extract display text from an inline token, stripping formatting markers."""
    if not token.children:
        return token.content or ""
    parts = []
    for child in token.children:
        if child.type == 'softbreak':
            parts.append(' ')
        elif child.content:
            parts.append(child.content)
    return "".join(parts)


def _detect_alignments(data_rows, num_cols):
    """Return per-column alignment ('left' or 'right').

    A column is right-aligned when every non-empty data cell looks numeric.
    """
    alignments = []
    for j in range(num_cols):
        cells = [r[j] for r in data_rows if j < len(r) and r[j].strip()]
        numeric = all(_NUMERIC_RE.match(c.strip()) for c in cells) if cells else False
        alignments.append('right' if numeric else 'left')
    return alignments


def _format_row(row, col_widths, num_cols, alignments):
    cells = []
    for j in range(num_cols):
        cell = row[j] if j < len(row) else ""
        if alignments[j] == 'right':
            cells.append(cell.rjust(col_widths[j]))
        else:
            cells.append(cell.ljust(col_widths[j]))
    return COL_GAP.join(cells)


def _append(result, text, color, font):
    attr = NSAttributedString.alloc().initWithString_attributes_(
        text, {
            NSForegroundColorAttributeName: color,
            NSFontAttributeName: font,
        }
    )
    result.appendAttributedString_(attr)
