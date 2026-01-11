#
# Ultra-simple LLM tool for the macOS clipboard
# (c) in 2024 Guido Appenzeller
#
# OpenAI API Key is taken from the environment variable OPENAI_API_KEY
#

import os
import argparse
import traceback
import threading

from macllm.core.shortcuts import ShortCut
from macllm.ui import MacLLMUI  # noqa: F401

from macllm.core.user_request import UserRequest
from macllm.core.chat_history import ConversationHistory
from macllm.core.llm_service import get_model_for_speed
from macllm.tags.base import TagPlugin

from quickmachotkey import quickHotKey, mask
from quickmachotkey.constants import kVK_ANSI_A, kVK_Space, cmdKey, controlKey, optionKey

macLLM = None

start_token = "@@"
alias_token = "@"

SYSTEM_PROMPT = """You are a helpful assistant.
- If the request refers to a context:... this is a reference to a context block.
- In most cases, you dont need to mention the context explicitly.
- If you refer to it, do it by name only. So for "context:clipboard" just say "the clipboard"
- If asked to just look at a context, just acknowledge it. A question will follow later.
- If the user's request is not clear, ask for clarification.
Conversation history follows below."""

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
        """Log exceptions with structured formatting and full stack trace."""
        if not self.debug:
            return
        
        exception_str = str(traceback.format_exc()).strip()
        print(f"{color.RED}Exception: {exception}{color.END}")
        print(f"{color.GREY}{exception_str}{color.END}")
        print(f"{color.GREY}---{color.END}")

    def show_instructions(self):
        print(f'Hotkey for quick entry window is ⌥-space (option-space)')
        print(f'To use via the clipboard, copy text starting with "@@"')

    def __init__(self, debug=False):
        self.debug = debug
        self.ui = MacLLMUI()
        self.ui.macllm = self
        self.req = 0

        self.ui.clipboardCallback = self.clipboard_changed
        
        # Initialize conversation history (multiple conversations)
        self.conversation_history = ConversationHistory()
        self.chat_history = self.conversation_history.get_current_conversation() or self.conversation_history.add_conversation()
        self.chat_history.ui_update_callback = self._update_ui_from_callback
        
        # Initialize metadata for UI display (default speed is Normal)
        self.llm_metadata = {'provider': 'OpenAI', 'model': get_model_for_speed('normal'), 'tokens': 0}
        self._prefix_index = []

    def handle_instructions(self, user_input):
        self.req = self.req+1
        user_input = user_input.strip()

        try:
            # Step 1: expand shortcut aliases (e.g. @@foo -> full text macros)
            expanded_input = ShortCut.expandAll(user_input)

            # Step 2: Build UserRequest and process all @tags
            request = UserRequest(expanded_input)
            if not request.process_tags(self.plugins, self.chat_history, self.debug_log, self.debug_exception, self._prefix_index):
                self.debug_log(f'Request #{self.req}: {user_input} - Abort on plugin failure', 1)
                return None

            # Step 3: Record user message (as typed, for UI display)
            self.chat_history.add_user_message(user_input)
            self.debug_log(f'Request #{self.req}: user_input={user_input}', 1)

            # Step 4: Select speed level
            if request.speed_level is not None:
                self.chat_history.speed_level = request.speed_level

            # Step 5: Ensure agent exists and update its model if speed changed
            if self.chat_history.agent is None:
                self.chat_history._create_agent()
            elif request.speed_level is not None:
                self.chat_history._create_agent()

            # Step 6: Run agent on background thread
            def run_agent():
                try:
                    self.chat_history.agent_status = ""
                    self._update_ui_from_callback()
                    
                    result = self.chat_history.agent.run(request.expanded_prompt, max_steps=10)
                    
                    if isinstance(result, str):
                        result = result.strip()
                    
                    if result:
                        self.chat_history.add_assistant_message(result)
                    else:
                        self.chat_history.add_assistant_message("Error: No output from agent")
                    
                    self.chat_history.agent_status = ""
                    self._update_ui_from_callback()
                    
                    self.debug_log(f'Output: {result}\n')
                except Exception as e:
                    self.debug_exception(e)
                    self.chat_history.add_assistant_message(f"Error: {str(e)}")
                    self.chat_history.agent_status = ""
                    self._update_ui_from_callback()
            
            thread = threading.Thread(target=run_agent, daemon=True)
            thread.start()
            
            return None  # Async operation, no immediate return value
            
        except Exception as e:
            self.debug_exception(e)
            return None
    
    def _update_ui_from_callback(self):
        if self.ui:
            self.ui.request_update()
        
    def clipboard_changed(self):
        txt = self.ui.read_clipboard()

        if txt.startswith(start_token):
            out = self.handle_instructions(txt[len(start_token):])
            if out is not None:  # Only update clipboard if operation succeeded
                self.ui.write_clipboard(out)    

def main():
    global macLLM

    parser = argparse.ArgumentParser(description="macLLM - a simple LLM tool for the macOS clipboard")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    args = parser.parse_args()

    if args.version:
        print(MacLLM.version)
        return

    macLLM = MacLLM(debug=args.debug)

    if args.debug:
        macLLM.debug_log(f"Debug mode is enabled (v {MacLLM.version})", 2)

    # Load plugins first so that configuration tags found in shortcut files
    # can be handled by their respective plugins during shortcut parsing.
    macLLM.plugins = TagPlugin.load_plugins(macLLM)

    # Build prefix index once: list of (prefix, plugin) for fast startswith matching
    prefix_pairs = []
    for plugin in macLLM.plugins:
        for prefix in plugin.get_prefixes():
            prefix_pairs.append((prefix, plugin))
    # Sort by descending prefix length to prefer longer, more specific matches first
    prefix_pairs.sort(key=lambda x: len(x[0]), reverse=True)
    macLLM._prefix_index = prefix_pairs

    # Now initialise shortcuts – this will invoke *on_config_tag()* on any
    # plugin that registered configuration prefixes.
    ShortCut.init_shortcuts(macLLM)
    
    macLLM.show_instructions()
    macLLM.ui.start(dont_run_app=False)

if __name__ == "__main__":
    main()

# Helper for tests

def create_macllm(debug: bool = False, start_ui: bool = False):
    mac = MacLLM(debug=debug)
    mac.plugins = TagPlugin.load_plugins(mac)
    ShortCut.init_shortcuts(mac)
    if start_ui:
        mac.ui.start(dont_run_app=True)
    return mac

