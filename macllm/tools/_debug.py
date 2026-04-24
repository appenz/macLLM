"""macllm_tool: drop-in replacement for ``@smolagents.tool`` with debug logging
and live tool-call tracking on the current conversation."""

import functools
import inspect
import threading
import warnings

# smolagents warns about non-@tool decorators for its remote executor,
# which we don't use. Suppress globally before any tool is registered.
warnings.filterwarnings("ignore", message=".*has decorators other than @tool")

from smolagents import tool as _smolagents_tool

_tool_conv_id = threading.local()


def _get_conversation(conv_id: str | None = None):
    """Return a conversation by *conv_id*, or fall back to thread / active tab."""
    try:
        from macllm.core.context import get_current_conversation
        conv = get_current_conversation(conv_id)
        if conv is not None and hasattr(conv, 'tool_calls'):
            return conv
    except Exception:
        pass
    return None


def set_tool_message(message: str, conv_id: str | None = None) -> None:
    """Override the display message of the most recent live tool-call entry.

    Call this from inside a ``@macllm_tool``-decorated function to replace
    the auto-generated "Using tool: ..." text with something more descriptive.
    *conv_id* is optional; when omitted the id captured by the decorator is used.
    """
    if conv_id is None:
        conv_id = getattr(_tool_conv_id, 'value', None)
    conv = _get_conversation(conv_id)
    if conv is not None:
        conv.update_last_tool_message(message)


def macllm_tool(fn):
    """Register a smolagents tool and log every invocation via ``MacLLM.debug_log``."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        from macllm.macllm import MacLLM
        app = MacLLM._instance
        dbg = getattr(app, "debug_log", None) if app is not None else None
        if dbg is not None:
            dbg(f"[tool] {fn.__name__} called")

        conv = _get_conversation()
        conv_id = getattr(conv, 'conv_id', None) if conv is not None else None
        _tool_conv_id.value = conv_id

        if conv is not None:
            conv.add_tool_call(fn.__name__, f"Using tool: {fn.__name__}")

        return fn(*args, **kwargs)
    wrapper.__signature__ = inspect.signature(fn)
    wrapper.__qualname__ = fn.__qualname__
    del wrapper.__wrapped__
    return _smolagents_tool(wrapper)
