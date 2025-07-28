import os
import pytest

from macllm.macllm import create_macllm
from macllm.models.fake_connector import FakeConnector
from macllm.models.openai_connector import OpenAIConnector


@pytest.fixture
def app_fake():
    app = create_macllm(debug=True)
    # Swap in fake connector
    app.llm = FakeConnector()
    return app


@pytest.fixture
def app_real():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set – skipping external tests")
    # create_macllm will construct the default OpenAIConnector
    return create_macllm(debug=True)


def pytest_configure(config):
    # Register custom marker so pytest doesn't warn
    config.addinivalue_line("markers", "external: tests that hit external services") 