"""Thread-local conversation context for parallel tab execution.

Agent threads set their conversation at entry via ``set_current_conversation``.
Tools and callbacks call ``get_current_conversation`` to reach the correct
conversation without knowing about threading.  Main-thread callers (e.g. tag
plugins) fall back to ``MacLLM._instance.chat_history``.
"""

import threading

_thread_context = threading.local()


def set_current_conversation(conv):
    """Bind *conv* as the current conversation for this thread."""
    _thread_context.conversation = conv


def get_current_conversation():
    """Return the conversation for the calling thread.

    Checks the thread-local first (set by agent threads), then falls back
    to the active conversation on the MacLLM singleton (main thread).
    """
    conv = getattr(_thread_context, 'conversation', None)
    if conv is not None:
        return conv
    from macllm.macllm import MacLLM
    return MacLLM._instance.chat_history
