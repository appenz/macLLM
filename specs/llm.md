# LLM Integration

## Overview

macLLM uses LiteLLM through `macllm/core/llm_service.py`.

The main runtime path is agent-based:

- runtime config provides API keys
- `refresh_models()` builds a `MODELS` map for `fast`, `normal`, and `slow`
- `MacLLMAgent` selects `MODELS[speed]` and passes that model to smolagents

## Design

Model IDs are configured in code, not in TOML. Config provides keys and directory settings, while model selection remains part of application logic.

This keeps the public user-facing speed tiers stable even if the backing provider or model name changes.

`generate()` exists as a direct LiteLLM wrapper, but it is not the main request path used by the app.

## Speed Model

Speed selection enters through request processing:

- `/fast` maps to `fast`
- `/slow` and `/think` map to `slow`
- conversation state stores the selected speed tier

That tier is resolved once when the agent instance is created.
