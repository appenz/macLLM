# Agent Architecture

## Overview

macLLM agents are built on top of [smolagents](https://github.com/huggingface/smolagents) `ToolCallingAgent`. Each agent follows a **plan-then-act loop**: it periodically creates/updates a plan, then executes tool calls in an Action/Observation cycle until it calls `final_answer`.

## Class Hierarchy

```
smolagents.ToolCallingAgent
  └── MacLLMAgent          (macllm/agents/base.py)
        ├── MacLLMDefaultAgent   (macllm/agents/default.py)
        └── MacLLMSmolAgent      (macllm/agents/smolagent.py)
```

**`MacLLMAgent`** is the base class. It wires up model selection (via `speed`), tool resolution, token tracking, and step callbacks. Subclasses declare three class-level identity attributes—`macllm_name`, `macllm_description`, `macllm_tools`—and pass behavioural config through `super().__init__()`.

**`MacLLMDefaultAgent`** (`macllm_name="default"`) uses a custom system prompt from `macllm/agents/prompts/default.yaml` and injects its own `custom_instructions`.

**`MacLLMSmolAgent`** (`macllm_name="smolagent"`) is a lightweight alternative that passes `prompt_templates=None`, causing smolagents to use its own built-in prompt templates instead. It shares the same `custom_instructions` and tool set as `MacLLMDefaultAgent`. 

## Registry

`macllm/agents/__init__.py` auto-discovers all `MacLLMAgent` subclasses by scanning `macllm/agents/*.py`. They are registered by `macllm_name` into `AGENT_REGISTRY`. The factory function `create_agent()` in `agent_service.py` instantiates an agent class with a given speed and token callback.

## System Prompt and Custom Instructions

The system prompt is a Jinja2 template (see `default.yaml`). At render time smolagents injects:

- **`{{ tools }}`** — descriptions of all registered tools.
- **`{{ managed_agents }}`** — descriptions of any sub-agents.
- **`{{ custom_instructions }}`** — free-form text inserted near the end of the prompt.

`custom_instructions` is where agent-specific behavioural rules live (e.g. "never create a file without explicit instructions"). It is passed as the `instructions` parameter to smolagents, which inserts it into the `{{ custom_instructions }}` placeholder in the template.

To customise an agent's behaviour: edit `custom_instructions` for rules/personality, or edit `default.yaml` for structural changes to the prompt (planning format, few-shot examples, etc.).

## Planning

`planning_interval` (default 3) controls how often the agent replans. At each planning step the agent produces a facts survey and a numbered plan. The step callback in `agent_service.py` parses the plan text and feeds it to `AgentStatusManager` for live display.

## Tool Resolution

Each subclass lists tool names in `macllm_tools` (e.g. `"web_search"`, `"read_full_file"`). `MacLLMAgent.__init__` resolves these to actual `@tool`-decorated functions from `macllm.tools`.

## Adding a New Agent

1. Create `macllm/agents/<name>.py` with a `MacLLMAgent` subclass.
2. Set `macllm_name`, `macllm_description`, and `macllm_tools`.
3. In `__init__`, pass `custom_instructions` and optionally `prompt_templates` to `super().__init__()`.
4. The registry picks it up automatically.
