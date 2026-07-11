from markdown_it import MarkdownIt
from Cocoa import NSAttributedString
from Foundation import NSMutableAttributedString

from macllm.markdown.blocks import (
    render_heading, render_paragraph, render_list,
    render_fence, render_blockquote, apply_block_margins,
)
from macllm.markdown.table import render_table
from macllm.markdown.spacing import gap_before, gap_after

BLOCK_DISPATCH = {
    'heading_open': render_heading,
    'paragraph_open': render_paragraph,
    'bullet_list_open': render_list,
    'ordered_list_open': render_list,
    'table_open': render_table,
}


class MarkdownRenderer:
    def __init__(self):
        self.md = MarkdownIt().enable("table")
        self.last_block_infos = []

    def render(self, text, color):
        text = text.rstrip('\n')
        tokens = self.md.parse(text)
        self.last_block_infos = []

        blocks = []
        i = 0
        while i < len(tokens):
            token = tokens[i]
            block_id = None

            if token.type in ('fence', 'code_block'):
                attr_str, i, block_id = render_fence(tokens, i, color)
            elif token.type == 'blockquote_open':
                attr_str, i, block_id = render_blockquote(tokens, i, color)
            elif token.type in BLOCK_DISPATCH:
                attr_str, i = BLOCK_DISPATCH[token.type](tokens, i, color)
            else:
                i += 1
                continue

            if attr_str and attr_str.length() > 0:
                blocks.append((token.type, attr_str, block_id))

        result = NSMutableAttributedString.alloc().init()
        for idx, (token_type, attr_str, block_id) in enumerate(blocks):
            prev_type = blocks[idx - 1][0] if idx > 0 else None
            next_type = blocks[idx + 1][0] if idx + 1 < len(blocks) else None
            before = gap_before(prev_type, token_type)
            after = gap_after(token_type, next_type)
            attr_str = apply_block_margins(attr_str, before, after)

            if idx > 0:
                nl = NSAttributedString.alloc().initWithString_("\n")
                result.appendAttributedString_(nl)

            start_pos = result.length()
            result.appendAttributedString_(attr_str)

            if block_id is not None:
                self.last_block_infos.append(
                    (block_id, start_pos, attr_str.length()))

        return result
