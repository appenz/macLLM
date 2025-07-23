#
# Shortcuts for LLM expansion
# (c) in 2023 Guido Appenzeller
#

import os
import sys
from pathlib import Path
import tomllib

# Class that handles shortcuts and the actions to be taken

class ShortCut:
    shortcuts = []
    macllm = None

    # Class method to expand all shortcuts in the text

    @classmethod
    def expandAll(cls, text):
        for s in cls.shortcuts:
            text = s.expand(text)
        return text

    @classmethod
    def read_shortcuts_file(cls, file_path, debug=False):
        """Read shortcuts from a TOML file and return the number of shortcuts processed."""
        if not os.path.exists(file_path):
            return 0

        # Skip non-TOML files
        if not file_path.endswith('.toml'):
            if debug:
                print(f"Skipping non-TOML file: {file_path}")
            return 0
            
        try:
            with open(file_path, "rb") as f:
                config = tomllib.load(f)
            
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
                #print(f"Added shortcut: {trigger} -> {prompt}")
                shortcuts_count += 1
            
            if debug:
                cls.macllm.debug_log(f"Found {shortcuts_count} shortcuts.",0)
            return shortcuts_count
            
        except tomllib.TOMLDecodeError as e:
            if debug:
                print(f"Error parsing TOML file {file_path}: {str(e)}")
            return 0
        except Exception as e:
            if debug:
                print(f"Error reading shortcuts from {file_path}: {str(e)}")
            return 0

    @classmethod
    def init_shortcuts(cls, macllm):

        cls.macllm = macllm
        
        # Get the application directory
        if getattr(sys, 'frozen', False):
            # If the application is run as a bundle
            app_dir = os.path.dirname(sys.executable)
        else:
            # If run from a Python interpreter
            app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Use config_dirs from macllm if available, otherwise use defaults
        config_dirs = getattr(macllm, 'config_dirs', [
            os.path.join(app_dir, "../config"),                # App config dir
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
                    cls.read_shortcuts_file(config_file, macllm.debug)
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
