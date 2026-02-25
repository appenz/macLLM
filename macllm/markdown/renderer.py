from markdown_it import MarkdownIt
from Cocoa import NSAttributedString
from Foundation import NSMutableAttributedString

from macllm.markdown.blocks import render_heading, render_paragraph, render_list, render_fence
from macllm.markdown.table import render_table

BLOCK_DISPATCH = {
    'heading_open': render_heading,
    'paragraph_open': render_paragraph,
    'bullet_list_open': render_list,
    'ordered_list_open': render_list,
    'table_open': render_table,
}

SELF_CLOSING_DISPATCH = {
    'fence': render_fence,
    'code_block': render_fence,
}

# Block types that get an extra blank line before and after for breathing room.
EXTRA_SPACING_TYPES = {'table_open'}


class MarkdownRenderer:
    def __init__(self):
        self.md = MarkdownIt().enable("table")

    def render(self, text, color):
        text = text.rstrip('\n')
        tokens = self.md.parse(text)
        result = NSMutableAttributedString.alloc().init()

        i = 0
        first_block = True
        prev_type = None
        while i < len(tokens):
            token = tokens[i]

            if token.type in BLOCK_DISPATCH:
                attr_str, i = BLOCK_DISPATCH[token.type](tokens, i, color)
            elif token.type in SELF_CLOSING_DISPATCH:
                attr_str, i = SELF_CLOSING_DISPATCH[token.type](tokens, i, color)
            else:
                i += 1
                continue

            if attr_str and attr_str.length() > 0:
                if not first_block:
                    extra = (token.type in EXTRA_SPACING_TYPES
                             or prev_type in EXTRA_SPACING_TYPES)
                    spacing = "\n\n" if extra else "\n"
                    nl = NSAttributedString.alloc().initWithString_(spacing)
                    result.appendAttributedString_(nl)
                result.appendAttributedString_(attr_str)
                prev_type = token.type
                first_block = False

        return result
