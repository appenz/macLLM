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
    
    @classmethod
    def find_shortcuts(cls, text: str) -> list[tuple[int, int, str]]:
        """
        Find all shortcuts in the text and return their positions and content.
        
        Returns list of (start_pos, end_pos, shortcut_text) tuples.
        Shortcuts are identified by:
        1. @ followed by non-whitespace characters until whitespace
        2. @" followed by characters until " or newline
        3. @ followed by characters with backslash-escaped spaces
        
        Args:
            text: The text to search for shortcuts
            
        Returns:
            List of (start_pos, end_pos, shortcut_text) tuples
        """
        shortcuts = []
        i = 0
        n = len(text)
        
        while i < n:
            # Find next @
            while i < n and text[i] != '@':
                i += 1
            
            if i >= n:
                break
                
            start = i
            
            # Check for quoted shortcut @"
            if i + 1 < n and text[i + 1] == '"':
                i += 2  # Skip @"
                quote_start = i
                while i < n and text[i] != '"' and text[i] != '\n':
                    i += 1
                if i < n and text[i] == '"':
                    # Strip quotes: keep @ but remove the surrounding quotes
                    shortcut_content = text[quote_start:i]
                    shortcut_text = '@' + shortcut_content
                    shortcuts.append((start, i + 1, shortcut_text))
                    i += 1
                else:
                    # Unclosed quote - treat as regular shortcut
                    shortcut_content = text[quote_start:i]
                    shortcut_text = '@' + shortcut_content
                    shortcuts.append((start, i, shortcut_text))
            else:
                # Regular shortcut - find end
                i += 1  # Skip @
                shortcut_chars = []
                while i < n:
                    if text[i] == '\\' and i + 1 < n and text[i + 1].isspace():
                        # Backslash-escaped space - add space to shortcut, skip backslash
                        shortcut_chars.append(text[i + 1])  # Add the space
                        i += 2
                    elif text[i].isspace():
                        # Unescaped space - end of shortcut
                        break
                    else:
                        shortcut_chars.append(text[i])
                        i += 1
                
                if len(shortcut_chars) > 0:  # At least one character after @
                    shortcut_text = '@' + ''.join(shortcut_chars)
                    shortcuts.append((start, i, shortcut_text))
        
        return shortcuts

    def process_plugins(self, plugins, debug_logger=None, debug_exception=None):
        """
        Process the request through all registered plugins.
        
        Finds shortcuts in the expanded prompt and processes them through plugins.
        Replaces shortcuts in place while preserving all other text exactly.
        
        Args:
            plugins: List of MacLLMPlugin instances to process
            debug_logger: Optional debug logging function
            debug_exception: Optional exception logging function
            
        Returns:
            bool: True if all plugins processed successfully, False if any plugin failed
        """
        shortcuts = self.find_shortcuts(self.expanded_prompt)
        
        # Process shortcuts in reverse order to maintain positions
        for start, end, shortcut_text in reversed(shortcuts):
            for plugin in plugins:
                if any(shortcut_text.startswith(prefix) for prefix in plugin.get_prefixes()):
                    try:
                        # Create a temporary request to get the expansion
                        temp_request = UserRequest("")
                        temp_request.expanded_prompt = shortcut_text
                        temp_request.context = ""
                        temp_request.needs_image = False
                        
                        plugin.expand(shortcut_text, temp_request)
                        
                        # Replace the shortcut with expanded content
                        replacement = temp_request.expanded_prompt + temp_request.context
                        self.expanded_prompt = (
                            self.expanded_prompt[:start] + 
                            replacement + 
                            self.expanded_prompt[end:]
                        )
                        
                        # Update image flag if needed
                        if temp_request.needs_image:
                            self.needs_image = True
                            
                    except Exception as e:
                        if debug_exception:
                            debug_exception(e)
                        if debug_logger:
                            debug_logger(f"Aborting request due to plugin error: {str(e)}", 2)
                        return False  # Indicate failure
                    break
        
        return True  # Indicate success 