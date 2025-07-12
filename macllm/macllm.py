#
# Ultra-simple LLM tool for the macOS clipboard
# (c) in 2024 Guido Appenzeller
#
# OpenAI API Key is taken from the environment variable OPENAI_API_KEY
#

import os
import argparse

from core.shortcuts import ShortCut
from ui import MacLLMUI
from core.user_request import UserRequest
from core.chat_history import ChatHistory
from shortcuts.base import ShortcutPlugin
from shortcuts.url_plugin import URLPlugin
from shortcuts.file_plugin import FilePlugin
from shortcuts.clipboard_plugin import ClipboardPlugin
from shortcuts.image_plugin import ImagePlugin
from models.openai_connector import OpenAIConnector

# Note: quickmachotkey needs to be imported after the ui.py file is imported. No idea why.
from quickmachotkey import quickHotKey, mask
from quickmachotkey.constants import kVK_ANSI_A, kVK_Space, cmdKey, controlKey, optionKey

macLLM = None

start_token = "@@"
alias_token = "@"

# Class defining ANSI color codes for terminal output
class color:
   RED = '\033[91m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   BLUE = '\033[94m'
   BOLD = '\033[1m'
   GREY = '\033[90m'
   UNDERLINE = '\033[4m'
   END = '\033[0m'

# Define the hotkey: option-space
@quickHotKey(virtualKey=kVK_Space, modifierMask=mask(optionKey))
# Ctrl-command-a instead
#@quickHotKey(virtualKey=kVK_ANSI_A, modifierMask=mask(cmdKey, controlKey))

def handler():
    global macLLM
    macLLM.ui.hotkey_pressed()

class MacLLM:

    # Watch the clipboard for the trigger string "@@" and if you find it run through GPT
    # and write the result back to the clipboard

    version = "0.2.0"

    def debug_log(self, message: str, level: int = 0):
        """Structured debug logging with color-coded levels."""
        if not self.debug:
            return
            
        colors = {
            0: color.GREY,    # Grey for general info
            1: color.BOLD,    # Black/bold for important info
            2: color.RED      # Red for errors/warnings
        }
        
        color_code = colors.get(level, color.GREY)
        print(f"{color_code}{message}{color.END}")
    
    def debug_exception(self, exception):
        """Log exceptions with structured formatting."""
        if not self.debug:
            return
            
        print(f"{color.RED}--- Error ----------------------------{color.END}")
        print(f"{exception}")

    def show_instructions(self):
        print(f'Hotkey for quick entry window is ⌥-space (option-space)')
        print(f'To use via the clipboard, copy text starting with "@@"')

    def __init__(self, model, debug=False):
        self.debug = debug
        self.ui = MacLLMUI()
        self.ui.macllm = self
        self.req = 0

        self.ui.clipboardCallback = self.clipboard_changed
        
        # Initialize chat history
        self.chat_history = ChatHistory()
        
        # Initialize plugins
        self.plugins = [
            URLPlugin(),
            FilePlugin(),
            ClipboardPlugin(self.ui),
            ImagePlugin(self)
        ]
        
        # Initialize LLM after debug_log method is available
        self.llm = OpenAIConnector(model=model, debug_logger=self.debug_log if debug else None)

    def handle_instructions(self, text):
        self.req = self.req+1
        text = text.strip()
        txt = ShortCut.expandAll(text)
        self.debug_log(f'Request #{self.req}: {txt}', 1)
        
        # Add user message to chat history
        self.chat_history.add_entry("user", txt)
        
        # Create request object and process plugins
        request = UserRequest(txt)
        if not request.process_plugins(self.plugins, self.debug_log, self.debug_exception):
            return None  # Abort the entire operation

        # Use image generation if needed
        if request.needs_image:
            # Find the ImagePlugin to get the image path
            image_plugin = next((p for p in self.plugins if isinstance(p, ImagePlugin)), None)
            image_path = image_plugin.tmp_image if image_plugin else "/tmp/macllm.png"
            out = self.llm.generate_with_image(request.expanded_prompt + request.context, image_path)
        else:                        
            self.debug_log(f'Sending text length {len(request.expanded_prompt + request.context)} to {self.llm.model}.')
            out = self.llm.generate(request.expanded_prompt + request.context).strip()
            
        # Add assistant response to chat history
        if out is not None:
            self.chat_history.add_entry("assistant", out)
            
        self.debug_log(f'Output: {out.strip()}\n')
        return out
        
    def clipboard_changed(self):
        txt = self.ui.read_clipboard()

        if txt.startswith(start_token):
            out = self.handle_instructions(txt[len(start_token):])
            if out is not None:  # Only update clipboard if operation succeeded
                self.ui.write_clipboard(out)    

def main():
    global macLLM

    parser = argparse.ArgumentParser(description="macLLM - a simple LLM tool for the macOS clipboard")
    parser.add_argument("--model", type=str, default="gpt-4o", help="The LLM model to use")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    args = parser.parse_args()

    if args.version:
        print(MacLLM.version)
        return

    macLLM = MacLLM(model=args.model, debug=args.debug)
    
    if args.debug:
        macLLM.debug_log(f"Debug mode is enabled (v {MacLLM.version})", 2)
    ShortCut.init_shortcuts(macLLM)
    macLLM.show_instructions()
    macLLM.ui.start()

if __name__ == "__main__":
    main()

