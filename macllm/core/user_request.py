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
            original_prompt: The original text from the user (may contain @ tags and / commands)
        """
        self.original_prompt = original_prompt  # The original text from the user (may contain @ tags and / commands)
        self.expanded_prompt = original_prompt  # Expanded text (may no longer contain @ tags or / commands)
        self.context = ""                       # Additional context to append
        self.needs_image = False                # Whether image generation is needed
        self.images = []                        # PIL Images to pass to the agent (e.g. clipboard images)
        self.speed_level = None                 # Speed preference for this request if provided
        self.agent_name = None                  # Agent type for this request (set by @agent: tag)
    
    @classmethod
    def find_shortcuts(cls, text: str) -> list[tuple[int, int, str]]:
        """
        Find all tags/commands in the text and return their positions and content.
        
        Returns list of (start_pos, end_pos, tag_text) tuples.
        Tags/commands are identified by:
        1. @ or / followed by non-whitespace characters until whitespace
        2. @" or /" followed by characters until " or newline
        3. @ or / followed by characters with backslash-escaped spaces
        
        Args:
            text: The text to search for tags/commands
            
        Returns:
            List of (start_pos, end_pos, tag_text) tuples
        """
        shortcuts = []
        i = 0
        n = len(text)
        
        while i < n:
            # Find next @ or /
            while i < n and text[i] != '@' and text[i] != '/':
                i += 1
            
            if i >= n:
                break
                
            start = i
            prefix_char = text[i]  # '@' or '/'
            
            # Check for quoted tag @" or /"
            if i + 1 < n and text[i + 1] == '"':
                i += 2  # Skip @" or /"
                quote_start = i
                while i < n and text[i] != '"' and text[i] != '\n':
                    i += 1
                if i < n and text[i] == '"':
                    # Strip quotes: keep prefix but remove the surrounding quotes
                    shortcut_content = text[quote_start:i]
                    shortcut_text = prefix_char + shortcut_content
                    shortcuts.append((start, i + 1, shortcut_text))
                    i += 1
                else:
                    # Unclosed quote - treat as regular tag
                    shortcut_content = text[quote_start:i]
                    shortcut_text = prefix_char + shortcut_content
                    shortcuts.append((start, i, shortcut_text))
            else:
                # Regular tag - find end
                i += 1  # Skip @ or /
                shortcut_chars = []
                while i < n:
                    if text[i] == '\\' and i + 1 < n and text[i + 1].isspace():
                        # Backslash-escaped space - add space to tag, skip backslash
                        shortcut_chars.append(text[i + 1])  # Add the space
                        i += 2
                    elif text[i].isspace():
                        # Unescaped space - end of tag
                        break
                    else:
                        shortcut_chars.append(text[i])
                        i += 1
                
                if len(shortcut_chars) > 0:  # At least one character after @ or /
                    shortcut_text = prefix_char + ''.join(shortcut_chars)
                    shortcuts.append((start, i, shortcut_text))
        
        return shortcuts

    def process_tags(self, plugins, conversation, debug_logger=None, debug_exception=None, prefix_index=None):
        """
        Process the user prompt through all registered TagPlugins.

        The method scans *expanded_prompt* for @tags (context) and /commands, calls the corresponding
        plugin's *expand()* method which may add context to *conversation*, and
        replaces the tag/command in-place with the string returned by the plugin.

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
            if prefix_index is not None:
                matched = False
                for prefix, plugin in prefix_index:
                    if shortcut_text.startswith(prefix):
                        try:
                            replacement = plugin.expand(shortcut_text, conversation, self)
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
                        matched = True
                        break
                if matched:
                    continue
            # Fallback to scanning plugins in order
            for plugin in plugins:
                if any(shortcut_text.startswith(prefix) for prefix in plugin.get_prefixes()):
                    try:
                        replacement = plugin.expand(shortcut_text, conversation, self)
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