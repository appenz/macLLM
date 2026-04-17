"""Fixtures for UI tests.

Re-exports the ``ui`` and ``_macllm_app`` fixtures from the harness module
so that any test in ``test/ui/`` can simply declare ``def test_foo(ui):``.
"""

from macllm.utils.uitest_harness import _macllm_app, ui  # noqa: F401
