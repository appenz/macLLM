"""Tests for macllm.core.device_context."""

import re

import pytest

from macllm.core import device_context as dc


@pytest.fixture(autouse=True)
def _reset_device_context_cache():
    dc._CACHE_EXPIRES = 0.0
    dc._CACHE_LOC_TEXT = "Unknown"
    dc._CACHE_GPS_TEXT = "Unknown"
    yield
    dc._CACHE_EXPIRES = 0.0
    dc._CACHE_LOC_TEXT = "Unknown"
    dc._CACHE_GPS_TEXT = "Unknown"


def test_get_device_context_lines_present():
    text = dc.get_device_context()
    assert "Current time:" in text
    assert "Location:" in text
    assert "GPS:" in text
    assert re.search(
        r"Current time: (Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday), \d{4}-\d{2}-\d{2}",
        text,
    ), text


def test_get_device_context_uses_cached_location(monkeypatch):
    calls = {"n": 0}

    def fake_fetch():
        calls["n"] += 1
        return "Test City, TS, Testland", "1.0000, 2.0000"

    monkeypatch.setattr(dc, "_fetch_location_uncached", fake_fetch)

    t1 = dc.get_device_context()
    t2 = dc.get_device_context()
    assert calls["n"] == 1
    assert "Location: Test City, TS, Testland" in t1
    assert "GPS: 1.0000, 2.0000" in t1
    assert t1 == t2


class _FakePlacemark:
    """Synthetic CLPlacemark; missing attrs return None like Apple does."""

    def __init__(self, **fields) -> None:
        self._fields = fields

    def __getattr__(self, attr: str):
        def call():
            return self._fields.get(attr)

        return call


def test_format_placemark_joins_all_populated_fields():
    pm = _FakePlacemark(
        name="US Post Office",
        thoroughfare="Market St",
        locality="San Francisco",
        administrativeArea="CA",
        country="United States",
    )
    s = dc._format_placemark_description(pm)
    assert s == "US Post Office, Market St, San Francisco, CA, United States"


def test_format_placemark_drops_thoroughfare_when_name_contains_address():
    pm = _FakePlacemark(
        name="140 Campo Bello Ln",
        subThoroughfare="140",
        thoroughfare="Campo Bello Ln",
        locality="Menlo Park",
        country="United States",
    )
    s = dc._format_placemark_description(pm)
    assert s == "140 Campo Bello Ln, Menlo Park, United States"


def test_format_placemark_unknown_when_empty():
    pm = _FakePlacemark()
    assert dc._format_placemark_description(pm) == "Unknown"


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
        assert "The user's current time & location" in prompt
        assert "Current time:" in prompt
        assert "Location:" in prompt
        assert "GPS:" in prompt
    finally:
        MacLLM._instance = None
