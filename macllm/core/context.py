"""Conversation context: registry + thread-local fallback.

Every ``Conversation`` is registered by its ``conv_id`` at creation time.
Tools resolve the owning conversation via an explicit *conv_id* when
available, falling back to the thread-local binding set by agent threads.
"""

import threading

_thread_context = threading.local()
_registry: dict = {}  # conv_id -> Conversation


def register_conversation(conv) -> None:
    _registry[conv.conv_id] = conv


def unregister_conversation(conv) -> None:
    _registry.pop(conv.conv_id, None)


def set_current_conversation(conv):
    """Bind *conv* as the current conversation for this thread."""
    _thread_context.conversation = conv


def get_current_conversation(conv_id: str | None = None):
    """Return a conversation by *conv_id*, or fall back to thread-local / active tab.

    Resolution order:
    1. Explicit *conv_id* → registry lookup.
    2. Thread-local (set by agent threads via ``set_current_conversation``).
    3. The UI-active conversation on the ``MacLLM`` singleton (main-thread callers).
    """
    if conv_id is not None:
        conv = _registry.get(conv_id)
        if conv is not None:
            return conv

    conv = getattr(_thread_context, 'conversation', None)
    if conv is not None:
        return conv

    try:
        from macllm.macllm import MacLLM
        if MacLLM._instance is not None:
            return MacLLM._instance.chat_history
    except Exception:
        pass
    return None
