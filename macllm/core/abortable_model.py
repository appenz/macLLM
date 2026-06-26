"""Abort-aware wrapper around a smolagents Model.

Runs each ``generate()`` call in a disposable daemon thread so the
calling (agent) thread can bail out as soon as the conversation's
``abort_event`` is set — without waiting for the HTTP round-trip to
finish.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any
from macllm.core.conversationlog import current_activity_trace

if TYPE_CHECKING:
    from smolagents.models import ChatMessage
    from macllm.core.chat_history import Conversation


class AgentInterrupted(RuntimeError):
    """Raised by AbortableModel when the conversation's abort_event fires."""


class AbortableModel:
    """Proxy that makes any smolagents ``Model`` cancellable via a
    ``threading.Event``.

    All attribute access that is not overridden here is forwarded to
    the wrapped model so that ``model_id``, ``api_key``, etc. remain
    accessible.
    """

    def __init__(
        self,
        model: Any,
        abort_event: threading.Event,
        conversation: Conversation | None = None,
    ) -> None:
        self._model = model
        self._abort_event = abort_event
        self._conversation = conversation

    # ------------------------------------------------------------------
    # generate — blocking call made cancellable
    # ------------------------------------------------------------------

    def generate(self, *args: Any, **kwargs: Any) -> "ChatMessage":
        if self._abort_event.is_set():
            raise AgentInterrupted("Agent interrupted.")

        trace_node = self._start_trace_node(kwargs)
        result_holder: list[Any] = [None]
        error_holder: list[BaseException | None] = [None]
        done = threading.Event()

        def _do_generate() -> None:
            try:
                result_holder[0] = self._model.generate(*args, **kwargs)
            except BaseException as exc:
                error_holder[0] = exc
            finally:
                done.set()

        thread = threading.Thread(target=_do_generate, daemon=True)
        thread.start()

        while not done.is_set():
            if self._abort_event.wait(timeout=0.1):
                self._finish_trace_node(trace_node, failed=True, close=True)
                raise AgentInterrupted("Agent interrupted.")
            if done.is_set():
                break

        if error_holder[0] is not None:
            self._finish_trace_node(trace_node, failed=True, close=True)
            raise error_holder[0]
        self._finish_trace_node(trace_node, failed=False, close=False)
        return result_holder[0]

    def _start_trace_node(self, kwargs: dict[str, Any]):
        trace = current_activity_trace(getattr(self._conversation, "conversation_log", []))
        if trace is None:
            return None
        label = "Final answer" if self._is_final_answer_call(kwargs) else "Thinking"
        node = trace.start_model_call(label)
        self._conversation._notify_ui()
        return node

    def _finish_trace_node(self, node, *, failed: bool, close: bool) -> None:
        trace = current_activity_trace(getattr(self._conversation, "conversation_log", []))
        if trace is None or node is None:
            return
        if close:
            trace.close_node(node, state="error" if failed else "success")
        else:
            trace.finish_model_call(node, state="error" if failed else "success")
        self._conversation._notify_ui()

    @staticmethod
    def _is_final_answer_call(kwargs: dict[str, Any]) -> bool:
        tools = kwargs.get("tools_to_call_from") or []
        for tool in tools:
            name = getattr(tool, "name", None)
            if name == "final_answer":
                return True
        return False

    # ------------------------------------------------------------------
    # generate_stream — yield chunks, checking abort between each
    # ------------------------------------------------------------------

    def generate_stream(self, *args: Any, **kwargs: Any) -> Any:
        if self._abort_event.is_set():
            raise AgentInterrupted("Agent interrupted.")
        for chunk in self._model.generate_stream(*args, **kwargs):
            if self._abort_event.is_set():
                raise AgentInterrupted("Agent interrupted.")
            yield chunk

    # ------------------------------------------------------------------
    # Proxy everything else to the wrapped model
    # ------------------------------------------------------------------

    def __getattr__(self, name: str) -> Any:
        return getattr(self._model, name)
