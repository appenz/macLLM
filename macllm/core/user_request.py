class UserRequest:
    """
    Represents a user request that can be processed by macLLM plugins.

    Holds the original user prompt and tracks how it is rewritten as plugins
    expand @ tags into plain instructions or run options. External data is not
    attached here; tools return observations during the agent loop.
    """

    def __init__(self, original_prompt: str):
        """
        Initialize a new user request.

        Args:
            original_prompt: The original text from the user (may contain @ tags and / commands)
        """
        self.original_prompt = original_prompt
        self.expanded_prompt = original_prompt
        self.speed_level = None
        self.agent_name = None
        self.no_tools = False

    @classmethod
    def find_shortcuts(cls, text: str) -> list[tuple[int, int, str]]:
        """
        Find all tags/commands in the text and return their positions and content.

        Returns list of (start_pos, end_pos, tag_text) tuples.
        Tags/commands are identified by:
        1. @ or / followed by non-whitespace characters until whitespace
        2. @" or /" followed by characters until " or newline
        3. @ or / followed by characters with backslash-escaped spaces
        """
        shortcuts = []
        i = 0
        n = len(text)

        while i < n:
            while i < n and text[i] != '@' and text[i] != '/':
                i += 1

            if i >= n:
                break

            start = i
            prefix_char = text[i]

            if i + 1 < n and text[i + 1] == '"':
                i += 2
                quote_start = i
                while i < n and text[i] != '"' and text[i] != '\n':
                    i += 1
                if i < n and text[i] == '"':
                    shortcut_content = text[quote_start:i]
                    shortcut_text = prefix_char + shortcut_content
                    shortcuts.append((start, i + 1, shortcut_text))
                    i += 1
                else:
                    shortcut_content = text[quote_start:i]
                    shortcut_text = prefix_char + shortcut_content
                    shortcuts.append((start, i, shortcut_text))
            else:
                i += 1
                shortcut_chars = []
                while i < n:
                    if text[i] == '\\' and i + 1 < n and text[i + 1].isspace():
                        shortcut_chars.append(text[i + 1])
                        i += 2
                    elif text[i].isspace():
                        break
                    else:
                        shortcut_chars.append(text[i])
                        i += 1

                if len(shortcut_chars) > 0:
                    shortcut_text = prefix_char + ''.join(shortcut_chars)
                    shortcuts.append((start, i, shortcut_text))

        return shortcuts

    def process_tags(self, plugins, conversation, debug_logger=None, debug_exception=None, prefix_index=None):
        """
        Process the user prompt through all registered TagPlugins.

        Scans *expanded_prompt* for @tags and /commands, calls the matching
        plugin's *expand()* method, and replaces the token in-place with the
        string returned by the plugin. Plugins may set run options on this
        request; they must not attach external data payloads.
        """
        shortcuts = self.find_shortcuts(self.expanded_prompt)

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
                    break
        return True

    process_plugins = process_tags
