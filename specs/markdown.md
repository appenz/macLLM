# Markdown Rendering

Assistant messages are rendered as Markdown via the `macllm/markdown/` package.
Parsing is handled by `markdown-it-py`; rendering produces `NSAttributedString`
for display in the Cocoa text view.

## Architecture

The renderer is dispatch-based.

- `MarkdownRenderer` parses markdown into tokens
- block tokens are dispatched through `BLOCK_DISPATCH`
- self-closing tokens are dispatched through `SELF_CLOSING_DISPATCH`
- each renderer consumes a token range and returns attributed text plus the next token index

Rendering is split by concern:

- `blocks.py` handles headings, paragraphs, lists, and fenced code
- `inline.py` handles text spans, bold, soft breaks, inline code, and links
- `link.py` handles markdown links and bare URL detection
- `table.py` handles markdown tables as monospaced aligned text

This keeps markdown parsing centralized while allowing rendering behavior to be specialized by element type.

## Rendering Choices

The renderer does not aim for pixel-perfect HTML-style markdown. It makes a small number of
display-oriented choices that fit the Cocoa text view well.

- lists use hanging indents so wrapped lines align under the text rather than under the bullet
- list items use tab stops (bullet/number + `\t`) so item text starts at a fixed column regardless
  of marker width (e.g. "1." vs "10." align identically)
- lists are visually inset from body text with a base indent (`LIST_BASE_INDENT`)
- lists get vertical breathing room: `paragraphSpacingBefore` on the first item and
  `paragraphSpacing` on every item for subtle inter-item and after-list separation
- code blocks use monospaced text
- tables are rendered as aligned monospaced text rather than as native table widgets
- bare URLs are linkified even when they are not written as markdown links
- tables get extra spacing around them so they read as separate blocks

The main specialized rendering choice is tables: they are indented, slightly smaller, numerically aligned where possible, and visually truncated on overflow while preserving the underlying text for copy/paste.

## Integration

`MainTextHandler.append_markdown()` in `macllm/ui/main_text.py` calls `render_markdown(...)`
and appends the resulting attributed string to the conversation view.
