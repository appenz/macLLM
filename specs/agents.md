# Agent Architecture

## Overview

macLLM agents are built on top of smolagents `ToolCallingAgent`.

The agent layer adds:

- a registry of named agent classes
- managed-agent delegation for domain-specific work
- a shared base class for model, tool, and prompt wiring
- a thin factory used by conversation state
- status and token callbacks integrated with the UI

## Managed Agents

Managed agents are regular `MacLLMAgent` subclasses used as delegated specialists.

This is the main architectural choice in the agent system. Top-level agents keep a small tool surface
and delegate specialized work, such as file or calendar tasks, to subagents with narrower instructions
and tool sets.

The parent lists subagents in `macllm_managed_agents`. The base class resolves those names from the registry,
instantiates the subagents, and passes them to smolagents as `managed_agents`.

At runtime, a parent agent delegates by sending a natural-language task to the managed agent.
The subagent runs its own tool loop and returns a report. Delegation is also surfaced to
`AgentStatusManager`, so the UI can show nested subagent activity.

### Registry and Factory

The registry lives in `macllm/agents/__init__.py`.

- `AGENT_REGISTRY` is the map from stable agent name to agent class
- `get_agent_class(name)` resolves a named agent
- `get_default_agent_class()` returns the default top-level agent

The factory lives in `macllm/core/agent_service.py`.

- `create_agent(...)` is the single runtime construction path used by conversation state

## Structure

The shared base class is `MacLLMAgent` in `macllm/agents/base.py`.

Its architectural contract is:

- agent identity is declared at the class level
- tool membership is declared symbolically and resolved centrally
- prompt structure and behavioral rules are configured separately
- planning and token accounting are reported through shared callbacks
- managed-agent composition is declared by name, not by direct object wiring

Prompt behavior is split between prompt templates and custom instructions. Planning status is reported
through `create_step_callback()`. Tool execution status is reported by tools themselves rather than being
inferred from smolagents action events.

## Current Agent Topology

- `default`: main top-level assistant; uses local prompt templates; delegates to `files` and `calendar`
- `smolagent`: alternate top-level assistant; uses smolagents default templates; delegates to `files`
- `files`: specialist for indexed files and notes
- `calendar`: specialist for calendar and scheduling work

## Agent Selection API

Agents can be selected per request through the `@agent:<name>` tag.

- the tag is implemented by `AgentTag` in `macllm/tags/agent_tag.py`
- it validates the name against `AGENT_REGISTRY`
- it stores the chosen name on `UserRequest`
- `MacLLM.handle_instructions()` applies that selection by updating `chat_history.agent_cls`
