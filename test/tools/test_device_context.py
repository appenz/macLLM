"""Tests for macllm.core.device_context."""

import re

import pytest

from macllm.core import device_context as dc


@pytest.fixture(autouse=True)
def _reset_device_context_cache():
    dc._CACHE_EXPIRES = 0.0
    dc._CACHE_LINE = "Unknown"
    yield
    dc._CACHE_EXPIRES = 0.0
    dc._CACHE_LINE = "Unknown"


def test_get_device_context_includes_current_time_line():
    text = dc.get_device_context()
    assert "Current time:" in text
    assert "Location:" in text
    # Weekday from strftime %A
    assert re.search(
        r"Current time: (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), \d{4}-\d{2}-\d{2}",
        text,
    ), text


def test_get_device_context_uses_cached_location(monkeypatch):
    calls = {"n": 0}

    def fake_fetch():
        calls["n"] += 1
        return "1.0000, 2.0000 — Test City, TS, Testland"

    monkeypatch.setattr(dc, "_fetch_location_line_uncached", fake_fetch)

    t1 = dc.get_device_context()
    t2 = dc.get_device_context()
    assert calls["n"] == 1
    assert "1.0000, 2.0000" in t1
    assert "1.0000, 2.0000" in t2


def test_format_placemark_includes_poi_name_when_distinct():
    from macllm.core.device_context import _format_placemark_description

    class PM:
        def name(self):
            return "US Post Office"

        def locality(self):
            return "San Francisco"

        def administrativeArea(self):
            return "CA"

        def country(self):
            return "United States"

        def subThoroughfare(self):
            return None

        def thoroughfare(self):
            return "Market St"

    s = _format_placemark_description(PM())
    assert "US Post Office" in s
    assert "San Francisco" in s


def test_format_placemark_unknown_when_empty():
    from macllm.core.device_context import _format_placemark_description

    class PM:
        def name(self):
            return ""

        def locality(self):
            return None

        def administrativeArea(self):
            return None

        def country(self):
            return None

        def subThoroughfare(self):
            return None

        def thoroughfare(self):
            return None

    assert _format_placemark_description(PM()) == "Unknown"


def test_default_agent_system_prompt_contains_gps_coordinates(monkeypatch):
    """Real CoreLocation call: assert the system prompt contains a GPS lat/long pair.

    May fail when Location Services are off, denied, or simply unable to obtain a fix.
    """
    from unittest.mock import MagicMock

    from macllm.core import llm_service
    from macllm.core.agent_service import create_agent
    from macllm.agents.default import MacLLMDefaultAgent
    from macllm.macllm import MacLLM

    dummy = MagicMock()
    monkeypatch.setitem(llm_service.MODELS, "normal", dummy)
    monkeypatch.setitem(llm_service.MODELS, "fast", dummy)
    monkeypatch.setitem(llm_service.MODELS, "slow", dummy)

    class DummyApp:
        pass

    MacLLM._instance = DummyApp()
    try:
        agent = create_agent(agent_cls=MacLLMDefaultAgent, speed="normal")
        prompt = agent.initialize_system_prompt()
        match = re.search(
            r"Location:\s*(-?\d+\.\d+),\s*(-?\d+\.\d+)",
            prompt,
        )
        assert match, (
            "Expected a 'Location: <lat>, <lon>' line with real GPS coordinates "
            f"in the system prompt; got:\n{prompt}"
        )
        lat = float(match.group(1))
        lon = float(match.group(2))
        assert -90.0 <= lat <= 90.0, f"latitude out of range: {lat}"
        assert -180.0 <= lon <= 180.0, f"longitude out of range: {lon}"
    finally:
        MacLLM._instance = None


def test_default_agent_system_prompt_includes_user_situation(monkeypatch):
    from unittest.mock import MagicMock

    from macllm.core import llm_service
    from macllm.core.agent_service import create_agent
    from macllm.agents.default import MacLLMDefaultAgent
    from macllm.macllm import MacLLM

    dummy = MagicMock()
    monkeypatch.setitem(llm_service.MODELS, "normal", dummy)
    monkeypatch.setitem(llm_service.MODELS, "fast", dummy)
    monkeypatch.setitem(llm_service.MODELS, "slow", dummy)

    class DummyApp:
        pass

    MacLLM._instance = DummyApp()
    try:
        agent = create_agent(agent_cls=MacLLMDefaultAgent, speed="normal")
        prompt = agent.initialize_system_prompt()
        assert "User's current time & location" in prompt
        assert "Current time:" in prompt
        assert "Location:" in prompt
    finally:
        MacLLM._instance = None
