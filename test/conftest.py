import pytest
from unittest.mock import Mock, patch

from macllm.macllm import create_macllm
from macllm.core import virtual_filesystem


@pytest.fixture(autouse=True)
def isolated_conversation_filesystems(tmp_path, monkeypatch):
    monkeypatch.setattr(
        virtual_filesystem, "get_storage_dir", lambda: tmp_path / "app"
    )


@pytest.fixture
def app_mocked():
    """Fixture for local tests - mocks LiteLLM calls."""
    with patch('macllm.core.llm_service.completion') as mock_completion:
        mock_response = Mock()
        mock_response.choices = [Mock(message=Mock(content="MOCK_RESPONSE"))]
        mock_response.usage = Mock(total_tokens=0)
        mock_completion.return_value = mock_response
        
        app = create_macllm(debug=True)
        app._llm_mock = mock_completion
        yield app


@pytest.fixture
def app_fake(app_mocked):
    """Backwards compatibility alias for app_mocked."""
    return app_mocked


@pytest.fixture
def app_real():
    """Fixture for external tests - calls real LLM APIs."""
    from macllm.core.config import get_runtime_config
    if not get_runtime_config().api_keys.openai:
        pytest.skip("openai API key not configured – skipping external tests")
    return create_macllm(debug=True)


def get_context_blocks_from_messages(messages: list[dict]) -> dict[str, str]:
    """Extract context blocks from messages array for test assertions."""
    import re
    
    context_blocks = {}
    
    for msg in messages:
        if msg.get("role") == "user":
            content = msg.get("content", "")
            pattern = re.compile(
                r"--- context:(?P<name>[^\s]+) ---\n(?P<content>.*?)\n--- end context:\1 ---",
                re.DOTALL,
            )
            for match in pattern.finditer(content):
                context_blocks[match.group("name")] = match.group("content")
    
    return context_blocks


def pytest_configure(config):
    config.addinivalue_line("markers", "external: tests that hit external services")
    config.addinivalue_line("markers", "uitest: tests that open the macLLM UI window")
    config.addinivalue_line("markers", "uitest_external: UI tests that call an external vision LLM")
