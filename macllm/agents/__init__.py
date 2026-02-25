"""Agent registry with auto-discovery.

Scans ``macllm/agents/*.py`` (excluding ``__init__.py`` and ``base.py``) for
:class:`MacLLMAgent` subclasses and registers them by ``macllm_name``.
"""

import importlib
import inspect
from pathlib import Path

from macllm.agents.base import MacLLMAgent

AGENT_REGISTRY: dict[str, type[MacLLMAgent]] = {}

_discovered = False


def _discover_agents():
    """Import all agent modules and populate :data:`AGENT_REGISTRY`."""
    global _discovered
    if _discovered:
        return
    _discovered = True

    agents_dir = Path(__file__).parent
    skip = {"__init__.py", "base.py"}

    for file_path in sorted(agents_dir.glob("*.py")):
        if file_path.name in skip:
            continue
        module_name = f"macllm.agents.{file_path.stem}"
        try:
            module = importlib.import_module(module_name)
            for _name, obj in inspect.getmembers(module, inspect.isclass):
                if (
                    issubclass(obj, MacLLMAgent)
                    and obj is not MacLLMAgent
                    and getattr(obj, "macllm_name", "")
                ):
                    AGENT_REGISTRY[obj.macllm_name] = obj
        except Exception as e:
            print(f"Warning: Could not import agent module {module_name}: {e}")


def get_agent_class(name: str) -> type[MacLLMAgent]:
    """Return the agent class registered under *name*.

    Raises :class:`KeyError` if no agent with that name exists.
    """
    _discover_agents()
    return AGENT_REGISTRY[name]


def get_default_agent_class() -> type[MacLLMAgent]:
    """Return the default agent class (``MacLLMDefaultAgent``)."""
    _discover_agents()
    return AGENT_REGISTRY["default"]


def list_agents() -> list[type[MacLLMAgent]]:
    """Return all registered agent classes."""
    _discover_agents()
    return list(AGENT_REGISTRY.values())
