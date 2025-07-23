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
        self.original_prompt = original_prompt  # The original text from the user (may contain @ tags)
        self.expanded_prompt = original_prompt  # Expanded text (may no longer contain @ tags)
        self.context = ""                       # Additional context to append
        self.needs_image = False                # Whether image generation is needed
    
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

    def process_tags(self, plugins, conversation, debug_logger=None, debug_exception=None):
        """
        Process the user prompt through all registered TagPlugins.

        The method scans *expanded_prompt* for @tags, calls the corresponding
        plugin's *expand()* method which may add context to *conversation*, and
        replaces the tag in-place with the string returned by the plugin.

        Args:
            plugins: List of TagPlugin instances.
            conversation: The current Conversation object.
            debug_logger: Optional debug log callback.
            debug_exception: Optional exception log callback.

        Returns:
            bool – True on success, False if any plugin raises and we abort.
        """
        shortcuts = self.find_shortcuts(self.expanded_prompt)

        # Replace from the back to preserve string offsets
        for start, end, shortcut_text in reversed(shortcuts):
            for plugin in plugins:
                if any(shortcut_text.startswith(prefix) for prefix in plugin.get_prefixes()):
                    try:
                        replacement = plugin.expand(shortcut_text, conversation)
                        self.expanded_prompt = (
                            self.expanded_prompt[:start]
                            + replacement
                            + self.expanded_prompt[end:]
                        )
                    except Exception as e:
                        if debug_exception:
                            debug_exception(e)
                        if debug_logger:
                            debug_logger(f"Aborting request due to plugin error: {str(e)}", 2)
                        return False
                    break  # Stop checking other plugins for this shortcut
        return True

    # Maintain backwards-compatibility name
    process_plugins = process_tags 