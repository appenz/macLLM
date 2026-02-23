# Markdown Rendering

Assistant messages are rendered as Markdown via the `macllm/markdown/` package. Parsing is handled by `markdown-it-py`; rendering produces `NSAttributedString` for display in the Cocoa `NSTextView`.

## Architecture

```
macllm/markdown/
  __init__.py       render_markdown(text, color) — public entry point
  renderer.py       MarkdownRenderer: parses tokens, dispatches to element modules
  inline.py         Bold, plain text, softbreak, inline code
  blocks.py         Headings, paragraphs, bullet/ordered lists, fenced code blocks
  table.py          Monospaced column-aligned tables
```

The renderer parses Markdown into a token stream and walks it with a dispatch table (`BLOCK_DISPATCH`, `SELF_CLOSING_DISPATCH`). Each token type maps to a render function that consumes a range of tokens and returns `(NSAttributedString, next_index)`.

## Adding a New Element

1. Write a render function in the appropriate module (or create a new one).
2. Add an entry to `BLOCK_DISPATCH` or `SELF_CLOSING_DISPATCH` in `renderer.py`.

No parser changes are needed — `markdown-it-py` already tokenises the full Markdown spec.

## Tables

Tables render as monospaced, column-aligned text at a slightly smaller font size (11.5pt vs 13pt body) with an 8pt left indent. Numeric columns are right-aligned. Overflow is handled via `NSLineBreakByTruncatingTail` so the display truncates with "..." but copy/paste captures the full content.

## Lists

Bullet and ordered lists use `NSParagraphStyle` with `firstLineHeadIndent` / `headIndent` to create a hanging indent — wrapped lines align with the text after the bullet, not under it. Nested lists increase the indent.

## Integration

`MainTextHandler.append_markdown()` in `macllm/ui/main_text.py` calls `render_markdown(text, color)` and appends the result to the text view's storage.
