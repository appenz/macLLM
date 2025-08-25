#
# Ultra-simple LLM tool for the macOS clipboard
# (c) in 2024 Guido Appenzeller
#
# OpenAI API Key is taken from the environment variable OPENAI_API_KEY
#

import os
import argparse
import traceback

from macllm.core.shortcuts import ShortCut
from macllm.ui import MacLLMUI  # noqa: F401

from macllm.core.user_request import UserRequest
from macllm.core.chat_history import ConversationHistory
from macllm.tags.base import TagPlugin
from macllm.models.openai_connector import OpenAIConnector
from macllm.core.model_connector import ModelConnector
from macllm.models.llm_config import llmConfig

from quickmachotkey import quickHotKey, mask
from quickmachotkey.constants import kVK_ANSI_A, kVK_Space, cmdKey, controlKey, optionKey

# LLM configuration constants for different speed levels
SLOW_CONFIG = llmConfig(provider="OpenAI", model="gpt-5", reasoning_effort="medium", priority="auto")
NORMAL_CONFIG = llmConfig(provider="OpenAI", model="gpt-5", reasoning_effort="low", priority="auto")
FAST_CONFIG = llmConfig(provider="OpenAI", model="gpt-5-nano", reasoning_effort="minimal", priority="auto")

macLLM = None

start_token = "@@"
alias_token = "@"

system_prompt = """
You are a helpful assistant.
- If the user refers to a RESOURCE:... this is a reference to a resource block.
- In most cases, you dont need to mention the resource.
- If you refer to it, do it by name only. So for "RESOURCE:clipboard" just say "the clipboard"
- If asked to just look at a resource, just acknowledge it. A question will follow later.
- If the user's request is not clear, ask for clarification.
Conversation history follows below.
"""

context_start = "\n\n--- RESOURCE BLOCKS START HERE ---\n"

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
        
        # Initialize lightweight placeholder for UI (Normal). Real connector is built per request.
        self.llm = ModelConnector(model=FAST_CONFIG.model)
        self.llm.provider = FAST_CONFIG.provider
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
                return None  # Abort on plugin failure

            # Step 3: Record user message (original and expanded)
            self.chat_history.add_chat_entry("user", user_input, request.expanded_prompt)

            context = self.chat_history.get_context_history_text()

            if context:
                context = "\n" + context_start + context

            # Step 4: Compose full prompt for LLM (context + chat history)
            request_text = (
                system_prompt
                + "\n"
                + self.chat_history.get_chat_history_expanded()
                + context
            )
            self.debug_log(f'Request #{self.req}: {request_text}', 1)

            # Step 5: Select LLM config based on conversation/request speed and create connector
            # If the request has a speed preference from tags, update the conversation's sticky setting now
            if request.speed_level is not None:
                self.chat_history.speed_level = request.speed_level

            speed = (self.chat_history.speed_level or "normal").lower()
            if speed == "fast":
                selected = FAST_CONFIG
            elif speed == "slow":
                selected = SLOW_CONFIG
            else:
                selected = NORMAL_CONFIG

            # Build a real connector for this request when needed.
            # If we are using the lightweight placeholder (base ModelConnector)
            # or an actual OpenAI connector, build a fresh OpenAI connector
            # from the selected config. Otherwise (e.g. tests using FakeConnector),
            # reuse the injected connector.
            if isinstance(self.llm, OpenAIConnector) or type(self.llm) is ModelConnector:
                llm = OpenAIConnector(
                    model=selected.model,
                    priority=selected.priority,
                    reasoning_effort=selected.reasoning_effort,
                    debug_logger=self.debug_log if self.debug else None,
                )
            else:
                llm = self.llm

            # Expose the active connector to the UI for accurate provider/model/tokens display
            self.llm = llm

            # Step 6: Decide whether to include image
            last_image = self.chat_history.get_context_last_image()
            if last_image is not None:
                image_path = "/tmp/macllm.png"
                try:
                    with open(image_path, "wb") as img_file:
                        img_file.write(last_image)
                except Exception as e:
                    self.debug_exception(e)
                    return None
                out = llm.generate_with_image(request_text, image_path)
            else:
                out = llm.generate(request_text)
                if isinstance(out, str):
                    out = out.strip()

            if out is not None:
                self.chat_history.add_chat_entry("assistant", out, out)  # assistant responses are already "expanded"
            else:
                self.chat_history.add_chat_entry("system", "Error: No output from LLM", "Error: No output from LLM")
        except Exception as e:
            self.debug_exception(e)
            return None

        self.debug_log(f'Output: {out.strip() if out else ""}\n')
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
    print("macLLM.ui.start")
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

