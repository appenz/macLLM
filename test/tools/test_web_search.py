import os
import sys

import pytest

from macllm.tools.web_search import web_search, reset_search_counter, _state
from macllm.core.agent_status import AgentStatusManager


class DummyApp:
    def __init__(self):
        self.status_manager = AgentStatusManager()


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
    
    # Temporarily remove the API key to avoid making real API calls
    original_key = os.environ.pop("BRAVE_API_KEY", None)
    
    try:
        # 48 + 2 = 50, which is not > 50, so limit check passes
        # but it should fail due to missing API key
        with pytest.raises(ValueError, match="BRAVE_API_KEY"):
            web_search(["query1", "query2"])
    finally:
        # Restore the key if it was set
        if original_key is not None:
            os.environ["BRAVE_API_KEY"] = original_key


def test_empty_queries():
    """Test that empty queries list returns appropriate message."""
    reset_search_counter()
    
    result = web_search([])
    assert result == "No queries provided."


def test_missing_api_key():
    """Test that missing API key raises an error."""
    reset_search_counter()
    
    # Temporarily remove the API key if set
    original_key = os.environ.pop("BRAVE_API_KEY", None)
    
    try:
        with pytest.raises(ValueError, match="BRAVE_API_KEY"):
            web_search(["test query"])
    finally:
        # Restore the key if it was set
        if original_key is not None:
            os.environ["BRAVE_API_KEY"] = original_key


@pytest.mark.external
def test_web_search_guido_plane():
    """Test searching for Guido Appenzeller's plane model."""
    if not os.getenv("BRAVE_API_KEY"):
        pytest.skip("BRAVE_API_KEY not set")
    
    reset_search_counter()
    result = web_search(["What model of plane did Guido Appenzeller fly to the Caribbean"])
    
    assert "SR22T" in result, f"Expected 'SR22T' in results, got: {result[:500]}..."
