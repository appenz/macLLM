import os
import re
from datetime import datetime

import pytest

from macllm.tools.time import get_current_time
from macllm.core.agent_service import create_agent
from macllm.core.agent_status import AgentStatusManager


class DummyApp:
    def __init__(self):
        self.status_manager = AgentStatusManager()


def test_get_current_time():
    from macllm.macllm import MacLLM
    
    MacLLM._instance = DummyApp()
    try:
        result = get_current_time()
        parsed = datetime.strptime(result, "%Y-%m-%d %H:%M:%S")
        now = datetime.now()
        assert abs((now - parsed).total_seconds()) < 2
    finally:
        MacLLM._instance = None


@pytest.mark.external
def test_agent_uses_time_tool():
    if not os.getenv("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")

    from macllm.macllm import MacLLM
    from macllm.agents.default import MacLLMDefaultAgent

    MacLLM._instance = DummyApp()
    try:
        agent = create_agent(agent_cls=MacLLMDefaultAgent, speed="normal")
        result = agent.run("What is the current time? Use the get_current_time tool.")
        has_iso_date = re.search(r"\d{4}-\d{2}-\d{2}", result)
        has_time = re.search(r"\d{1,2}:\d{2}", result)
        assert has_iso_date or has_time, f"Expected date or time in response: {result}"
    finally:
        MacLLM._instance = None
