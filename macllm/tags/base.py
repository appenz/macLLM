import importlib
import inspect
from pathlib import Path
from macllm.core.chat_history import Conversation

class TagPlugin:
    """Base class for macLLM @tag expansion plugins."""
    _plugins: list["TagPlugin"] | None = None

    def __init__(self, macllm):
        # Keep reference to main app so a plugin can access UI / debug_log, etc.
        self.macllm = macllm

    # ---------------------------------------------------------------------
    # Dynamic plugin discovery / loading
    # ---------------------------------------------------------------------
    @classmethod
    def load_plugins(cls, macllm_instance):
        """Dynamically load all *_tag.py plugins in the *tags* directory."""
        if cls._plugins is not None:
            return cls._plugins

        plugins: list[TagPlugin] = []
        plugin_names: list[str] = []
        tags_dir = Path(__file__).parent

        for file_path in tags_dir.glob("*_tag.py"):
            module_name = f"macllm.tags.{file_path.stem}"
            try:
                module = importlib.import_module(module_name)
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, cls) and obj is not cls:
                        instance = obj(macllm_instance)
                        plugins.append(instance)
                        plugin_names.append(name)
            except ImportError as e:
                print(f"Warning: Could not import {module_name}: {e}")
            except Exception as e:
                print(f"Warning: Error loading plugin from {file_path.name}: {e}")

        cls._plugins = plugins

        if macllm_instance.debug and plugin_names:
            macllm_instance.debug_log(f"Loaded tag plugins: {', '.join(plugin_names)}")
        return cls._plugins

    # ------------------------------------------------------------------
    # Interface each concrete plugin must implement
    # ------------------------------------------------------------------
    def get_prefixes(self) -> list[str]:
        """Return the list of prefixes (e.g. ["@clipboard"]) that this plugin handles."""
        raise NotImplementedError

    def expand(self, tag: str, conversation: Conversation) -> str:  # noqa: D401
        """Expand *tag* inside *conversation*.

        1. The plugin should call `conversation.add_context(...)` as needed to
           store any additional data (clipboard text, file content, etc.).
        2. It must return the string that will replace the original tag in the
           user prompt (e.g. the context name returned by `add_context`).
        """
        raise NotImplementedError 