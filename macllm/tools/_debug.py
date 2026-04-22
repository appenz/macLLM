"""macllm_tool: drop-in replacement for ``@smolagents.tool`` with debug logging."""

import functools
import inspect
import warnings

# smolagents warns about non-@tool decorators for its remote executor,
# which we don't use. Suppress globally before any tool is registered.
warnings.filterwarnings("ignore", message="has decorators other than @tool")

from smolagents import tool as _smolagents_tool


def macllm_tool(fn):
    """Register a smolagents tool and log every invocation via ``MacLLM.debug_log``."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        from macllm.macllm import MacLLM
        app = MacLLM._instance
        if app is not None:
            app.debug_log(f"[tool] {fn.__name__} called")
        return fn(*args, **kwargs)
    wrapper.__signature__ = inspect.signature(fn)
    wrapper.__qualname__ = fn.__qualname__
    del wrapper.__wrapped__
    return _smolagents_tool(wrapper)
