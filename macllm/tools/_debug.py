"""macllm_tool: drop-in replacement for ``@smolagents.tool`` with debug logging
and live tool-call tracking on the current conversation."""

import functools
import inspect
import warnings

# smolagents warns about non-@tool decorators for its remote executor,
# which we don't use. Suppress globally before any tool is registered.
warnings.filterwarnings("ignore", message=".*has decorators other than @tool")

from smolagents import tool as _smolagents_tool


def _get_conversation():
    """Return the current conversation, or None if unavailable."""
    try:
        from macllm.core.context import get_current_conversation
        conv = get_current_conversation()
        if conv is not None and hasattr(conv, 'tool_calls'):
            return conv
    except Exception:
        pass
    return None


def set_tool_message(message: str) -> None:
    """Override the display message of the most recent live tool-call entry.

    Call this from inside a ``@macllm_tool``-decorated function to replace
    the auto-generated "Using tool: ..." text with something more descriptive.
    """
    conv = _get_conversation()
    if conv is not None:
        conv.update_last_tool_message(message)


def macllm_tool(fn):
    """Register a smolagents tool and log every invocation via ``MacLLM.debug_log``."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        from macllm.macllm import MacLLM
        app = MacLLM._instance
        if app is not None:
            app.debug_log(f"[tool] {fn.__name__} called")

        conv = _get_conversation()
        if conv is not None:
            conv.add_tool_call(fn.__name__, f"Using tool: {fn.__name__}")

        return fn(*args, **kwargs)
    wrapper.__signature__ = inspect.signature(fn)
    wrapper.__qualname__ = fn.__qualname__
    del wrapper.__wrapped__
    return _smolagents_tool(wrapper)
