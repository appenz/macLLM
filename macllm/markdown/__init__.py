from macllm.markdown.renderer import MarkdownRenderer

_renderer = MarkdownRenderer()

_code_blocks = {}
_code_block_expanded = {}
_next_block_id = 0
_code_block_ranges = []


def reset_code_blocks():
    """Clear the block registry and counter before a full re-render."""
    global _next_block_id
    _code_blocks.clear()
    _code_block_ranges.clear()
    _next_block_id = 0


def register_code_block(content):
    """Register a code block and return its unique ID."""
    global _next_block_id
    block_id = _next_block_id
    _next_block_id += 1
    _code_blocks[block_id] = content
    return block_id


def get_code_block_content(block_id):
    """Get the full content of a registered code block."""
    return _code_blocks.get(block_id)


def is_code_block_expanded(block_id):
    return _code_block_expanded.get(block_id, False)


def toggle_code_block(block_id):
    _code_block_expanded[block_id] = not _code_block_expanded.get(block_id, False)


def add_code_block_range(block_id, start, length):
    """Record the absolute text-storage range of a code block."""
    _code_block_ranges.append((block_id, start, length))


def get_code_block_ranges():
    return list(_code_block_ranges)


def get_code_block_count():
    return len(_code_block_ranges)


def get_last_render_block_infos():
    """Return block-range info from the most recent render() call."""
    return _renderer.last_block_infos


def render_markdown(text, color):
    """Render markdown text to an NSAttributedString."""
    return _renderer.render(text, color)
