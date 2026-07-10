import importlib

import pytest

from macllm.core.chat_history import Conversation
from macllm.core.context import set_current_conversation
from macllm.core.config import MacLLMConfig, ApiKeys
from macllm.tools.web_search import web_fetch, web_search, reset_search_counter, _state


class DummyApp:
    pass


@pytest.fixture(autouse=True)
def setup_macllm():
    """Set up MacLLM._instance for all tests in this module."""
    from macllm.macllm import MacLLM
    MacLLM._instance = DummyApp()
    yield
    MacLLM._instance = None


def test_reset_search_counter():
    """Test that reset_search_counter resets the counter to 0."""
    # Set counter to non-zero value
    _state["search_count"] = 10
    
    reset_search_counter()
    
    assert _state["search_count"] == 0


def test_search_limit_exceeded():
    """Test that exceeding the search limit raises an error."""
    reset_search_counter()
    
    # Set counter close to limit
    _state["search_count"] = 48
    
    # Requesting 3 more should exceed the limit of 50
    with pytest.raises(ValueError, match="Search limit exceeded"):
        web_search(["query1", "query2", "query3"])


def test_search_limit_exactly_at_max():
    """Test that exactly hitting the limit (50) passes the limit check."""
    reset_search_counter()
    
    # Set counter so that adding 2 queries hits exactly 50
    _state["search_count"] = 48
    
    ws_module = importlib.import_module("macllm.tools.web_search")
    original_get_runtime_config = ws_module.get_runtime_config
    ws_module.get_runtime_config = lambda: MacLLMConfig(api_keys=ApiKeys(brave=""))

    try:
        # 48 + 2 = 50, which is not > 50, so limit check passes
        # but it should fail due to missing API key
        with pytest.raises(ValueError, match="brave API key"):
            web_search(["query1", "query2"])
    finally:
        ws_module.get_runtime_config = original_get_runtime_config


def test_empty_queries():
    """Test that empty queries list returns appropriate message."""
    reset_search_counter()
    
    result = web_search([])
    assert result == "No queries provided."


def test_missing_api_key():
    """Test that missing API key raises an error."""
    reset_search_counter()
    
    ws_module = importlib.import_module("macllm.tools.web_search")
    original_get_runtime_config = ws_module.get_runtime_config
    ws_module.get_runtime_config = lambda: MacLLMConfig(api_keys=ApiKeys(brave=""))

    try:
        with pytest.raises(ValueError, match="brave API key"):
            web_search(["test query"])
    finally:
        ws_module.get_runtime_config = original_get_runtime_config


def test_web_search_returns_real_urls(monkeypatch):
    reset_search_counter()
    conversation = Conversation()
    set_current_conversation(conversation)

    ws_module = importlib.import_module("macllm.tools.web_search")
    monkeypatch.setattr(
        ws_module,
        "get_runtime_config",
        lambda: MacLLMConfig(api_keys=ApiKeys(brave="test-key")),
    )

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {
                "web": {
                    "results": [
                        {
                            "url": "https://example.com/long/path?a=1",
                            "title": "Example Page",
                            "description": "Useful snippet",
                        }
                    ]
                }
            }

    monkeypatch.setattr(ws_module.requests, "get", lambda *args, **kwargs: Response())

    try:
        result = web_search(["example query"])
    finally:
        set_current_conversation(None)

    assert "https://example.com/long/path?a=1" in result
    assert "Example Page" in result
    assert "Useful snippet" in result
    assert conversation.sources == []


def test_web_fetch_returns_chunks(monkeypatch):
    conversation = Conversation()
    url = "https://example.com/page"
    set_current_conversation(conversation)

    ws_module = importlib.import_module("macllm.tools.web_search")
    page_text = "x" * 12050

    class Response:
        text = f"<html><body><p>{page_text}</p></body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(ws_module.requests, "get", lambda *args, **kwargs: Response())

    try:
        first = web_fetch(url)
        second = web_fetch(url, start=10000)
    finally:
        set_current_conversation(None)

    assert first.startswith("[page truncated, chars 0-10000 of 12050]\n\n")
    assert first.endswith("x" * 10000)
    assert second == "x" * 2050


def test_web_fetch_caps_page_text(monkeypatch):
    conversation = Conversation()
    url = "https://example.com/large"
    set_current_conversation(conversation)

    ws_module = importlib.import_module("macllm.tools.web_search")
    page_text = "x" * 100001

    class Response:
        text = f"<html><body><p>{page_text}</p></body></html>"

        def raise_for_status(self):
            pass

    monkeypatch.setattr(ws_module.requests, "get", lambda *args, **kwargs: Response())

    try:
        result = web_fetch(url, start=90000)
    finally:
        set_current_conversation(None)

    assert result.startswith("[page truncated, chars 90000-100000 of 100000]\n\n")
    assert conversation.sources == [{"kind": "web", "ref": url}]


@pytest.mark.external
def test_web_search_guido_plane():
    """Test searching for Guido Appenzeller's plane model."""
    from macllm.core.config import get_runtime_config
    if not get_runtime_config().api_keys.brave:
        pytest.skip("brave API key not configured")
    
    reset_search_counter()
    result = web_search(["What model of plane did Guido Appenzeller fly to the Caribbean"])
    
    assert "SR22T" in result, f"Expected 'SR22T' in results, got: {result[:500]}..."
