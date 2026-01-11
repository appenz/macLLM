import os
import re
from datetime import datetime

import pytest

from macllm.tools.time import get_current_time
from macllm.core.agent_service import create_agent


def test_get_current_time():
    result = get_current_time()
    parsed = datetime.strptime(result, "%Y-%m-%d %H:%M:%S")
    now = datetime.now()
    assert abs((now - parsed).total_seconds()) < 2


@pytest.mark.external
def test_agent_uses_time_tool():
    if not os.getenv("OPENAI_API_KEY"):
        pytest.skip("OPENAI_API_KEY not set")
    
    agent = create_agent(speed="fast")
    result = agent.run("What is the current time? Use the get_current_time tool.")
    
    assert re.search(r"\d{4}-\d{2}-\d{2}", result)
