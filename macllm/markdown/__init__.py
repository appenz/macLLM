from macllm.markdown.renderer import MarkdownRenderer

_renderer = MarkdownRenderer()


def render_markdown(text, color):
    """Render markdown text to an NSAttributedString."""
    return _renderer.render(text, color)
