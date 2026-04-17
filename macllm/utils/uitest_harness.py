"""Pytest harness for UI tests.

Boots the real macLLM UI with ``dont_run_app=True`` so the test controls
the run loop, then exposes a ``UITestDriver`` via the ``ui`` fixture.

Screenshots are written to a temporary directory that is cleaned up
automatically by pytest's ``tmp_path_factory``.
"""

from __future__ import annotations

import pytest

from macllm.macllm import create_macllm
from macllm.utils.uitest import UITestDriver


@pytest.fixture(scope="session")
def _macllm_app():
    """Create a single MacLLM instance for the entire test session.

    The UI is started once and reused across tests.  Each individual test
    should use the ``ui`` fixture which resets state between tests.
    """
    app = create_macllm(debug=True, start_ui=True)
    app.ui.update_window()

    driver = UITestDriver(app.ui)
    driver.spin(0.3)
    return app, driver


@pytest.fixture
def ui(_macllm_app, tmp_path):
    """Per-test fixture: resets the UI to a clean state and provides a
    ``UITestDriver``.

    The ``tmp_path`` is available as ``ui.tmp_path`` for screenshot output;
    pytest removes it automatically after the session.
    """
    app, driver = _macllm_app

    # Ensure window is open and input is clear
    if not driver.window_open():
        app.ui.update_window()
        driver.spin(0.3)

    # Reset conversation and input for a clean slate
    app.chat_history.reset(clear_persisted=False)
    from macllm.ui.input_field import InputFieldHandler
    InputFieldHandler.clear_input_field(app.ui.input_field)
    InputFieldHandler.focus_input_field(app.ui.input_field)
    app.ui.update_window()
    driver.spin(0.2)

    # Attach tmp_path so tests can write screenshots there
    driver.tmp_path = tmp_path
    return driver
