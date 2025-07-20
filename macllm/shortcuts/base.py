from macllm.core.user_request import UserRequest
import importlib
import inspect
from pathlib import Path

class ShortcutPlugin:
    """Base class for macLLM shortcuts that handle @ tag expansions."""
    
    _plugins = None  # Class variable to store loaded plugins
    
    def __init__(self, macllm):
        """Initialize the plugin with a reference to the macLLM instance."""
        self.macllm = macllm
    
    @classmethod
    def load_plugins(cls, macllm_instance) -> list['ShortcutPlugin']:
        """
        Dynamically load all shortcut plugins in the shortcuts directory.
        Stores the plugins in the _plugins class variable and returns them.
        """
        if cls._plugins is not None:
            return cls._plugins
            
        plugins = []
        plugin_names = []
        shortcuts_dir = Path(__file__).parent
        
        # Get all Python files in the shortcuts directory that end with _plugin.py
        for file_path in shortcuts_dir.glob("*_plugin.py"):
            
            # Import the module
            module_name = f"macllm.shortcuts.{file_path.stem}"
            try:
                module = importlib.import_module(module_name)
                
                # Find all classes in the module that inherit from ShortcutPlugin
                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if (issubclass(obj, cls) and obj != cls):
                        # Instantiate the plugin with the macLLM instance
                        plugin_instance = obj(macllm_instance)
                        plugins.append(plugin_instance)
                        plugin_names.append(name)
                        
            except ImportError as e:
                print(f"Warning: Could not import {module_name}: {e}")
            except Exception as e:
                print(f"Warning: Error loading plugin from {file_path.name}: {e}")
        
        cls._plugins = plugins
        
        # Print loaded plugin names if debug logging is enabled
        if macllm_instance.debug and plugin_names:
            macllm_instance.debug_log(f"Loaded plugins: {', '.join(plugin_names)}")
        
        return cls._plugins
    
    def get_prefixes(self) -> list[str]:
        """Return list of prefixes this plugin handles."""
        pass
    
    def expand(self, word: str, request: UserRequest) -> None:
        """
        Expand a word that matches one of this plugin's prefixes.
        Modifies the request object directly instead of returning values.
        """
        pass 