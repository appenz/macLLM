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
from pathlib import Path

from macllm.ui import MacLLMUI  # noqa: F401

from macllm.core.user_request import UserRequest
from macllm.core.chat_history import ConversationHistory
from macllm.core.llm_service import get_model_for_speed, enable_litellm_debug, refresh_models
from macllm.core.memory import save_conversation, load_conversation
from macllm.core.agent_status import AgentStatusManager
from macllm.core.config import load_runtime_config
from macllm.core.skills import SkillsRegistry
from macllm.tags.base import TagPlugin

from quickmachotkey import quickHotKey, mask
from quickmachotkey.constants import kVK_ANSI_A, kVK_Space, cmdKey, controlKey, optionKey

macLLM = None

from macllm.agents.default import MacLLMDefaultAgent, CUSTOM_INSTRUCTIONS

# Backward-compat alias
SYSTEM_PROMPT = CUSTOM_INSTRUCTIONS

# Class defining ANSI color codes for terminal output
class color:
   RED = '\033[91m'
   GREEN = '\033[92m'
   YELLOW = '\033[93m'
   BLUE = '\033[94m'
   ORANGE = '\033[38;5;208m'
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
    _instance = None  # Singleton reference for global access

    version = "0.2.0"

    @classmethod
    def get_status_manager(cls) -> AgentStatusManager:
        """Get the current agent status manager."""
        return cls._instance.status_manager

    def debug_log(self, message: str, level: int = 0):
        """Structured debug logging with color-coded levels."""
        if not self.args.debug:
            return
            
        colors = {
            0: color.GREY,    # Grey for general info
            1: color.BOLD,    # Black/bold for important info
            2: color.RED,     # Red for errors/warnings
            3: color.ORANGE   # Orange for tool calls
        }
        
        color_code = colors.get(level, color.GREY)
        print(f"{color_code}{message}{color.END}")
    
    def debug_exception(self, exception):
        """Log exceptions with structured formatting and full stack trace."""
        if not self.args.debug:
            return
        
        exception_str = str(traceback.format_exc()).strip()
        print(f"{color.RED}Exception: {exception}{color.END}")
        print(f"{color.GREY}{exception_str}{color.END}")
        print(f"{color.GREY}---{color.END}")

    def check_path_in_active_conversations(self, path: str) -> bool:
        """Check if a path was explicitly referenced in any active conversation.
        
        Currently checks only the current conversation, but can be extended
        to check multiple parallel conversations in the future.
        """
        if self.chat_history and self.chat_history.has_path_in_context(path):
            return True
        return False

    def show_instructions(self):
        print(f'Hotkey for quick entry window is ⌥-space (option-space)')

    def _apply_index_dirs_from_config(self):
        from macllm.tags.file_tag import FileTag
        FileTag._indexed_directories = []
        for plugin in getattr(self, "plugins", []):
            for d in self.config.resolved_index_dirs():
                if hasattr(plugin, "on_config_tag"):
                    plugin.on_config_tag("@IndexFiles", d)

    def __init__(self, args=None):
        MacLLM._instance = self
        self.args = args or argparse.Namespace(debug=False, show_window_on_start=False)
        self.config = load_runtime_config()
        refresh_models()
        SkillsRegistry.reload()
        self.ui = MacLLMUI()
        self.ui.macllm = self
        self.req = 0

        # Initialize agent status manager for displaying progress
        self.status_manager = AgentStatusManager(ui_update_callback=self._update_ui_from_callback)
        
        # Agent thread tracking for abort support
        self._agent_thread = None
        self._abort_event = threading.Event()
        
        # Initialize conversation history (multiple conversations)
        self.conversation_history = ConversationHistory()
        self.chat_history = self.conversation_history.get_current_conversation() or self.conversation_history.add_conversation()
        self.chat_history.ui_update_callback = self._update_ui_from_callback

        self.ephemeral = bool(getattr(self.args, 'query', None))
        if not self.ephemeral:
            load_conversation(self.chat_history)
        
        # Initialize metadata for UI display (default speed is Normal)
        self.llm_metadata = {'provider': 'OpenAI', 'model': get_model_for_speed('normal'), 'input_tokens': 0, 'output_tokens': 0}
        self._prefix_index = []

    def is_agent_running(self):
        """Check if an agent is currently executing."""
        return self._agent_thread is not None and self._agent_thread.is_alive()

    def abort_agent(self):
        """Signal the running agent to abort after the current step completes.
        
        Uses smolagents' built-in interrupt_switch which causes the agent to
        raise AgentError at the start of the next step iteration.
        If a shell command approval is pending, auto-deny it to unblock
        the agent thread so the abort can proceed.
        """
        if not self.is_agent_running():
            return
        self._abort_event.set()
        if self.status_manager.pending_approval is not None:
            self.status_manager.resolve_approval("deny")
        if self.chat_history.agent:
            self.chat_history.agent.interrupt_switch = True
            for agent in getattr(self.chat_history.agent, 'managed_agents', {}).values():
                agent.interrupt_switch = True
        self.debug_log("Agent abort requested", 1)

    def _handle_abort_summary(self, task):
        """After an abort, ask the LLM to summarize what the agent found so far."""
        try:
            self.status_manager.set_plan("Summarizing...")
            self._update_ui_from_callback()
            summary_msg = self.chat_history.agent.provide_final_answer(task)
            content = summary_msg.content
            if isinstance(content, list):
                content = " ".join(
                    item.get("text", "") for item in content if isinstance(item, dict)
                )
            result = content.strip() if isinstance(content, str) else str(content)
            prefix = "**Interrupted.** The following is a partial answer based on what I found before being stopped:\n\n"
            self.chat_history.add_assistant_message(prefix + result if result else "[Interrupted]")
        except Exception as summary_error:
            self.debug_exception(summary_error)
            self.chat_history.add_assistant_message("[Interrupted]")
        if not self.ephemeral:
            save_conversation(self.chat_history)

    def handle_instructions(self, user_input):
        self.req = self.req+1
        user_input = user_input.strip()

        try:
            # Local command: reload merged config + skills.
            if user_input == "/reload":
                self.config = load_runtime_config()
                refresh_models()
                summary = SkillsRegistry.reload()
                self._apply_index_dirs_from_config()
                try:
                    from macllm.tags.file_tag import FileTag
                    FileTag._start_reindex()
                except Exception:
                    pass
                self.chat_history.add_user_message(user_input)
                self.chat_history.add_assistant_message(summary)
                self._update_ui_from_callback()
                if not self.ephemeral:
                    save_conversation(self.chat_history)
                return None

            # Step 1: expand slash skill invocations.
            expanded_input = SkillsRegistry.expand_manual_invocation(user_input)

            # Step 2: Build UserRequest and process all @tags
            request = UserRequest(expanded_input)
            if not request.process_tags(self.plugins, self.chat_history, self.debug_log, self.debug_exception, self._prefix_index):
                self.debug_log(f'Request #{self.req}: {user_input} - Abort on plugin failure', 1)
                return None

            # Step 3: Record user message (as typed, for UI display)
            self.chat_history.add_user_message(user_input)
            self.debug_log(f'Request #{self.req}: user_input={user_input}', 1)

            # Step 4: Select agent and speed level
            if request.agent_name is not None:
                from macllm.agents import get_agent_class
                self.chat_history.agent_cls = get_agent_class(request.agent_name)
            if request.speed_level is not None:
                self.chat_history.speed_level = request.speed_level

            # Step 5: Reset token count for this request
            self.llm_metadata['input_tokens'] = 0
            self.llm_metadata['output_tokens'] = 0
            
            # Step 6: Define token callback to update metadata and UI
            def token_callback(input_tokens: int, output_tokens: int):
                self.llm_metadata['input_tokens'] = input_tokens
                self.llm_metadata['output_tokens'] = output_tokens
                self._update_ui_from_callback()

            # Step 7: Recreate agent with fresh token callback for each request
            self.chat_history._create_agent(token_callback=token_callback)

            # Step 8: Run agent on background thread
            def run_agent():
                try:
                    self.ui.set_status_indicator(working=True)
                    self.status_manager.reset()
                    self._abort_event.clear()
                    
                    run_kwargs = dict(max_steps=10, reset=False)
                    if request.images:
                        run_kwargs["images"] = request.images
                    result = self.chat_history.agent.run(request.expanded_prompt, **run_kwargs)
                    
                    if isinstance(result, str):
                        result = result.strip()
                    
                    if result:
                        self.chat_history.add_assistant_message(result)
                    else:
                        self.chat_history.add_assistant_message("Error: No output from agent")
                    
                    if not self.ephemeral:
                        save_conversation(self.chat_history)
                    self.status_manager.reset()
                    
                    self.debug_log(f'Output: {result}\n')
                except Exception as e:
                    if self._abort_event.is_set():
                        self._handle_abort_summary(request.expanded_prompt)
                    else:
                        self.debug_exception(e)
                        self.chat_history.add_assistant_message(f"Error: {str(e)}")
                        if not self.ephemeral:
                            save_conversation(self.chat_history)
                    self.status_manager.reset()
                finally:
                    self._agent_thread = None
                    self._abort_event.clear()
                    self.ui.set_status_indicator(working=False)
                    self._update_ui_from_callback()
                    if getattr(self.args, 'query', None):
                        screenshot_path = getattr(self.args, 'screenshot', None)
                        self.ui.schedule_quit(screenshot_path=screenshot_path)
            
            self._agent_thread = threading.Thread(target=run_agent, daemon=True)
            self._agent_thread.start()
            
            return None  # Async operation, no immediate return value
            
        except Exception as e:
            self.debug_exception(e)
            return None
    
    def _update_ui_from_callback(self):
        if self.ui:
            self.ui.request_update()
        
def main():
    global macLLM

    parser = argparse.ArgumentParser(description="macLLM - a simple LLM tool for the macOS clipboard")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    parser.add_argument("--debuglitellm", action="store_true", help="Enable verbose LiteLLM debug logging")
    parser.add_argument("--version", action="store_true", help="Print version and exit")
    parser.add_argument("--show-window", action="store_true", dest="show_window_on_start", help="Open the window immediately on startup")
    parser.add_argument("--query", type=str, default=None, help="Auto-submit a query after the window opens (implies --show-window)")
    parser.add_argument("--screenshot", type=str, default=None, metavar="PATH",
                        help="After --query completes, capture the window to PATH and exit")
    args = parser.parse_args()

    if args.query:
        args.show_window_on_start = True

    if args.version:
        print(MacLLM.version)
        return

    macLLM = MacLLM(args=args)

    if args.debug:
        macLLM.debug_log(f"Debug mode is enabled (v {MacLLM.version})", 2)
    
    if args.debuglitellm:
        enable_litellm_debug()
        if args.debug:
            macLLM.debug_log("LiteLLM debug logging enabled", 2)

    # Load plugins first.
    macLLM.plugins = TagPlugin.load_plugins(macLLM)

    # Build prefix index once: list of (prefix, plugin) for fast startswith matching
    prefix_pairs = []
    for plugin in macLLM.plugins:
        for prefix in plugin.get_prefixes():
            prefix_pairs.append((prefix, plugin))
    # Sort by descending prefix length to prefer longer, more specific matches first
    prefix_pairs.sort(key=lambda x: len(x[0]), reverse=True)
    macLLM._prefix_index = prefix_pairs

    # Configure indexed directories from merged config.
    macLLM._apply_index_dirs_from_config()

    # Start periodic file index + embedding rebuild (first cycle runs immediately)
    from macllm.tags.file_tag import FileTag
    FileTag.start_index_loop()

    # Warn about deprecated shortcut files during transition.
    project_root = Path(__file__).resolve().parents[2]
    legacy = [
        project_root / "config" / "default_shortcuts.toml",
        project_root / "config" / "myshortcuts.toml",
    ]
    for p in legacy:
        if p.exists() and macLLM.args.debug:
            macLLM.debug_log(f"Deprecated shortcut file ignored: {p}", 1)
    
    if args.query:
        macLLM.ui.pending_query = args.query
        macLLM.ui.pending_screenshot = args.screenshot

    macLLM.show_instructions()
    macLLM.ui.start(dont_run_app=False)

if __name__ == "__main__":
    main()

# Helper for tests

def create_macllm(debug: bool = False, start_ui: bool = False):
    args = argparse.Namespace(debug=debug, show_window_on_start=False)
    mac = MacLLM(args=args)
    mac.plugins = TagPlugin.load_plugins(mac)
    mac._apply_index_dirs_from_config()
    from macllm.tags.file_tag import FileTag
    FileTag.build_index()
    if start_ui:
        mac.ui.start(dont_run_app=True)
    return mac

