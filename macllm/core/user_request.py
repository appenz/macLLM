class UserRequest:
    """
    Represents a user request that can be processed by macLLM plugins.
    
    This class holds the original user prompt and tracks how it gets transformed
    as plugins expand @ tags and add context. It also tracks whether image
    generation is needed for the final LLM request.
    """
    
    def __init__(self, original_prompt: str):
        """
        Initialize a new user request.
        
        Args:
            original_prompt: The original text from the user (may contain @ tags)
        """
        self.original_prompt = original_prompt
        self.expanded_prompt = original_prompt  # Current working text
        self.context = ""                       # Additional context to append
        self.needs_image = False               # Whether image generation is needed
    
    def process_plugins(self, plugins, debug_logger=None, debug_exception=None):
        """
        Process the request through all registered plugins.
        
        Iterates through each word in the expanded prompt and attempts to match
        it with plugin prefixes. When a match is found, the plugin's expand()
        method is called to modify this request object.
        
        Args:
            plugins: List of MacLLMPlugin instances to process
            debug_logger: Optional debug logging function
            debug_exception: Optional exception logging function
            
        Returns:
            bool: True if all plugins processed successfully, False if any plugin failed
        """
        words = self.expanded_prompt.split()
        for word in words:
            for plugin in plugins:
                if any(word.startswith(prefix) for prefix in plugin.get_prefixes()):
                    try:
                        plugin.expand(word, self)
                    except Exception as e:
                        if debug_exception:
                            debug_exception(e)
                        if debug_logger:
                            debug_logger(f"Aborting request due to plugin error: {str(e)}", 2)
                        return False  # Indicate failure
                    break
        return True  # Indicate success 