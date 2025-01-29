#
# Shortcuts for LLM expansion
# (c) in 2023 Guido Appenzeller
#

promptShortcuts = [
    ["@exp-email", "Write an email based on the following bullet points. Your email should be extremely concise. Avoid unnecessary words. Be friendly, enthusiastic and high energy. Your expanded email should not change the meaning from the bullet points.\n ---\n"],
    ["@exp", "Expand the following into paragraphs of text. The output should not consist of bullet points any more. Use extremely concise language. Your style should be sophisticated like The Economist or the Wall Street Journal. It's fine to use complex technical terms if needed. Avoid any unecessary words. Do not change the meaning of the text\n ---\n"],
    ["@fix-de", "Korrigiere alle Rechtschreib- und Grammatikfehler im folgenden deutschen Text:"],
    ["@fix-fr", "Corrigez toutes les fautes d'orthographe et de grammaire dans le texte en langue française suivant:"],
    ["@fix", "Correct any spelling or grammar mistakes in the following text:"],
    ["@rewrite", "Rewrite the following text but keep the same meaning and be extremely concise.\n---\n"],
    ["@tr-de", "Translate the following text into the German language. Reply only with the translation and nothing else.\n---\n"],
    ["@tr-fr", "Translate the following text into the French language. Reply only with the translation and nothing else.\n---\n"],
    ["@tr-es", "Translate the following text into the Spanish language. Reply only with the translation and nothing else.\n---\n"],
    ["@emojis", "Pick a sequence of up to 5 emojis that are relevant to the following text. Reply only with the emojis, i.e. up to five characters. Do not exmplain your choice or write any other text.\n---\n"],
    ["@emoji", "Pick an emoji that is relevant to the following text. Reply only with that emoji, i.e. a single character. Do not exmplain your choice or write any other text.\n---\n"],
    ["@linkedin", "List the job experience of this person, use one bullet point per job."],
    ["@slide", "Summarize the contents of this slide in a few bullet points. Each bullet point should fit on a single line."],
    ["@transcribe", "Precisely transcribe this image. Do not explain it. Reply only with the transcript of any text in the image and nothing else."],
]

# Class that handles shortcuts and the actions to be taken

class ShortCut:
    shortcuts = []

    # Class method to expand all shortcuts in the text

    @classmethod
    def expandAll(cls, text):
        for s in cls.shortcuts:
            text = s.expand(text)
        return text

    @classmethod
    def init_shortcuts(cls, macllm):
        # Initialize the shortcuts
        for p in promptShortcuts:
            ShortCut(p[0], p[1])

        import os
        import sys
        from pathlib import Path

        def read_shortcuts_file(file_path, debug=False):
            """Read shortcuts from a TOML file and return the number of shortcuts processed."""
            if not os.path.exists(file_path):
                return 0

            # Skip non-TOML files
            if not file_path.endswith('.toml'):
                if debug:
                    print(f"Skipping non-TOML file: {file_path}")
                return 0
                
            import toml
            try:
                with open(file_path, "r") as f:
                    config = toml.load(f)
                
                if 'shortcuts' not in config:
                    if debug:
                        print(f"No shortcuts table found in {file_path}")
                    return 0
                
                shortcuts_count = 0
                for shortcut in config['shortcuts']:
                    if len(shortcut) != 2:
                        if debug:
                            print(f"Invalid shortcut format in {file_path}: {shortcut}")
                        continue
                        
                    trigger, prompt = shortcut
                    if not isinstance(trigger, str) or not isinstance(prompt, str):
                        if debug:
                            print(f"Invalid shortcut types in {file_path}: {shortcut}")
                        continue
                        
                    if not trigger.startswith('@'):
                        if debug:
                            print(f"Trigger must start with @ in {file_path}: {trigger}")
                        continue
                        
                    ShortCut(trigger, prompt)
                    shortcuts_count += 1
                
                if debug:
                    print(f"Read {shortcuts_count} shortcuts from {file_path}")
                return shortcuts_count
                
            except toml.TomlDecodeError as e:
                if debug:
                    print(f"Error parsing TOML file {file_path}: {str(e)}")
                return 0
            except Exception as e:
                if debug:
                    print(f"Error reading shortcuts from {file_path}: {str(e)}")
                return 0

        # Get the application directory
        if getattr(sys, 'frozen', False):
            # If the application is run as a bundle
            app_dir = os.path.dirname(sys.executable)
        else:
            # If run from a Python interpreter
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Use config_dirs from macllm if available, otherwise use defaults
        config_dirs = getattr(macllm, 'config_dirs', [
            os.path.join(app_dir, "config"),                # App config dir
            os.path.expanduser("~/.config/macllm")          # User config dir
        ])

        # Read all files from both config directories
        for config_dir in config_dirs:
            if not os.path.exists(config_dir):
                continue
                
            # List all files in the directory
            try:
                files = [f for f in os.listdir(config_dir) if os.path.isfile(os.path.join(config_dir, f))]
                for file in files:
                    config_file = os.path.join(config_dir, file)
                    if macllm.debug:
                        print(f"Processing config file: {config_file}")
                    read_shortcuts_file(config_file, macllm.debug)
            except OSError:
                if macllm.debug:
                    print(f"Error accessing directory: {config_dir}")


    def __init__(self, trigger, prompt):
        self.trigger = trigger
        self.prompt = prompt
        self.shortcuts.append(self)

    # Find all occurrences of the trigger in the text and expand them
    def expand(self, text):
        return text.replace(self.trigger, self.prompt)
