"""Abort-aware wrapper around a smolagents Model.

Runs each ``generate()`` call in a disposable daemon thread so the
calling (agent) thread can bail out as soon as the conversation's
``abort_event`` is set — without waiting for the HTTP round-trip to
finish.
"""

from __future__ import annotations

import threading
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from smolagents.models import ChatMessage


class AgentInterrupted(RuntimeError):
    """Raised by AbortableModel when the conversation's abort_event fires."""


class AbortableModel:
    """Proxy that makes any smolagents ``Model`` cancellable via a
    ``threading.Event``.

    All attribute access that is not overridden here is forwarded to
    the wrapped model so that ``model_id``, ``api_key``, etc. remain
    accessible.
    """

    def __init__(self, model: Any, abort_event: threading.Event) -> None:
        self._model = model
        self._abort_event = abort_event

    # ------------------------------------------------------------------
    # generate — blocking call made cancellable
    # ------------------------------------------------------------------

    def generate(self, *args: Any, **kwargs: Any) -> "ChatMessage":
        if self._abort_event.is_set():
            raise AgentInterrupted("Agent interrupted.")

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
                raise AgentInterrupted("Agent interrupted.")
            if done.is_set():
                break

        if error_holder[0] is not None:
            raise error_holder[0]
        return result_holder[0]

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
