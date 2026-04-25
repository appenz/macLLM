"""Shared agent prompt templates from ``macllm/agents/prompts/default.yaml``.

Loaded once. Used by the default top-level agent and all specialist subagents so
nothing falls back to smolagents' bundled ``toolcalling_agent.yaml``.
"""

from __future__ import annotations

import yaml
from pathlib import Path

_PATH = Path(__file__).parent / "prompts" / "default.yaml"
MACLLM_AGENT_PROMPT_TEMPLATES: dict = yaml.safe_load(_PATH.read_text(encoding="utf-8"))
