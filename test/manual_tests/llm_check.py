#!/usr/bin/env python3
"""
Manual test script to verify LLM calls work correctly.
Run with: make test-llm QUERY="your query here" SPEED=fast|normal|slow
Add DEBUG_LITELLM=1 for verbose LiteLLM logging.
"""

import os

from litellm import completion

from macllm.core.llm_service import MODELS, enable_litellm_debug

# Get config from environment variables (set by Makefile)
QUERY = os.environ.get("QUERY", "What is 2 + 2? Answer with just the number.")
SPEED = os.environ.get("SPEED", "normal")
DEBUG_LITELLM = os.environ.get("DEBUG_LITELLM", "").lower() in ("1", "true", "yes")


def test_direct_litellm_call():
    """Test direct LiteLLM completion call."""
    if DEBUG_LITELLM:
        enable_litellm_debug()
    
    model = MODELS.get(SPEED)
    assert model is not None, f"Model for speed '{SPEED}' is not configured"
    
    print(f"\nModel: {model.model_id}")
    print(f"Query: {QUERY}")
    
    response = completion(
        model=model.model_id,
        messages=[{"role": "user", "content": QUERY}],
        api_key=model.api_key,
        api_base=getattr(model, 'api_base', None),
    )
    
    result = response.choices[0].message.content
    print(f"SUCCESS: {result}")
    
    assert result is not None, "Response should not be None"
