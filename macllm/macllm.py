#
# Ultra-simple LLM tool for the macOS clipboard
# (c) in 2024 Guido Appenzeller
#
# OpenAI API Key is taken from the environment variable OPENAI_API_KEY
#

import os
import argparse
import traceback
from pathlib import Path

from macllm.ui import MacLLMUI  # noqa: F401

from macllm.core.chat_history import ConversationHistory
from macllm.core.llm_service import get_model_for_speed, enable_litellm_debug, refresh_models
from macllm.core.memory import save_all_conversations, load_all_conversations
from macllm.core.config import load_runtime_config
from macllm.core.skills import SkillsRegistry
from macllm.tags.base import TagPlugin

from quickmachotkey import quickHotKey, mask
from quickmachotkey.constants import kVK_ANSI_A, kVK_Space, cmdKey, controlKey, optionKey

macLLM = None

from macllm.agents.default import MacLLMDefaultAgent  # noqa: F401

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

def handler():
    global macLLM
    macLLM.ui.hotkey_pressed()

class MacLLM:
    _instance = None  # Singleton reference for global access

    version = "0.2.0"

    def debug_log(self, message: str, level: int = 0):
        """Structured debug logging with color-coded levels."""
        if not self.args.debug:
            return
            
        colors = {
            0: color.GREY,
            1: color.BOLD,
            2: color.RED,
            3: color.ORANGE
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
        """Check if a path was explicitly referenced in any active conversation."""
        for conv in self.conversation_history.conversations:
            if conv.has_path_in_context(path):
                return True
        return False

    def show_instructions(self):
        print(f'Hotkey for quick entry window is ⌥-space (option-space)')

    def _apply_index_dirs_from_config(self):
        from macllm.tags.file_tag import FileTag
        FileTag._mount_points = {}
        FileTag._indexed_directories = []
        for name, path in self.config.resolved_index_dirs().items():
            if not os.path.isdir(path):
                self.debug_log(f"@IndexFiles: Not a directory – {path}", 2)
                continue
            FileTag._mount_points[name] = path
            if path not in FileTag._indexed_directories:
                FileTag._indexed_directories.append(path)

    def _set_ui_callbacks(self):
        """Ensure every conversation has the UI update callback."""
        for conv in self.conversation_history.conversations:
            conv.ui_update_callback = self._update_ui_from_callback

    def __init__(self, args=None):
        MacLLM._instance = self
        self.args = args or argparse.Namespace(debug=False, show_window_on_start=False)
        self.config = load_runtime_config()
        refresh_models()
        SkillsRegistry.reload()
        self.ui = MacLLMUI()
        self.ui.macllm = self
        self.req = 0

        # Initialize conversation history (multiple conversations)
        self.conversation_history = ConversationHistory()
        self.ephemeral = bool(getattr(self.args, 'query', None))
        if not self.ephemeral:
            loaded = load_all_conversations(self.conversation_history)
            if not loaded:
                self.conversation_history.add_conversation()
        else:
            self.conversation_history.add_conversation()
        self.chat_history = self.conversation_history.get_current_conversation()
        self._set_ui_callbacks()

        self._prefix_index = []

    def switch_to_conversation(self, index: int) -> bool:
        """Switch the active conversation by index."""
        if not self.ephemeral:
            save_all_conversations(self.conversation_history)
        if not self.conversation_history.set_active(index):
            return False
        self.chat_history = self.conversation_history.get_current_conversation()
        self.chat_history.ui_update_callback = self._update_ui_from_callback
        return True

    def new_conversation(self):
        """Create a new conversation, make it active, and save the old one."""
        if not self.ephemeral:
            save_all_conversations(self.conversation_history)
        conv = self.conversation_history.add_conversation()
        self.chat_history = conv
        self.chat_history.ui_update_callback = self._update_ui_from_callback
        self._update_ui_from_callback()

    def cycle_conversation(self, delta: int):
        """Cycle through conversations by *delta* (+1 = newer, -1 = older)."""
        if self.conversation_history.cycle(delta):
            if not self.ephemeral:
                save_all_conversations(self.conversation_history)
            self.chat_history = self.conversation_history.get_current_conversation()
            self.chat_history.ui_update_callback = self._update_ui_from_callback
            self._update_ui_from_callback()

    def delete_conversation(self, index: int):
        """Remove the conversation at *index* and switch to the new active one."""
        conv = self.conversation_history.conversations[index] if 0 <= index < len(self.conversation_history.conversations) else None
        if conv and conv.is_agent_running():
            conv.abort()
        if not self.conversation_history.remove_conversation(index):
            return
        self.chat_history = self.conversation_history.get_current_conversation()
        self.chat_history.ui_update_callback = self._update_ui_from_callback
        if not self.ephemeral:
            save_all_conversations(self.conversation_history)
        self._update_ui_from_callback()

    def _update_ui_from_callback(self):
        if self.ui:
            self.ui.request_update()
        
def _run_task_headless(args):
    """Run a task file headlessly and exit with the appropriate code."""
    import sys
    from macllm.core.task_runner import parse_task_file, apply_cli_overrides, run_task

    try:
        task = parse_task_file(args.task)
    except FileNotFoundError as e:
        sys.stderr.write(f"Error: {e}\n")
        sys.exit(1)

    apply_cli_overrides(task, args)

    if args.debuglitellm:
        enable_litellm_debug()

    exit_code = run_task(task, args)
    sys.exit(exit_code)


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
    parser.add_argument("-task", type=str, default=None, metavar="FILE",
                        help="Run a task file headlessly and exit")
    parser.add_argument("--token-budget", type=int, default=None, dest="token_budget",
                        help="Max tokens before tool use is disabled (overrides task file)")
    parser.add_argument("--time-budget", type=int, default=None, dest="time_budget",
                        help="Max seconds before tool use is disabled (overrides task file)")
    parser.add_argument("--logfile", type=str, default=None,
                        help="Write task output to file instead of stdout (overrides task file)")
    args = parser.parse_args()

    if args.query:
        args.show_window_on_start = True

    if args.version:
        print(MacLLM.version)
        return

    # Headless task runner — bypass UI entirely
    if args.task:
        _run_task_headless(args)
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

    # Build prefix index once
    prefix_pairs = []
    for plugin in macLLM.plugins:
        for prefix in plugin.get_prefixes():
            prefix_pairs.append((prefix, plugin))
    prefix_pairs.sort(key=lambda x: len(x[0]), reverse=True)
    macLLM._prefix_index = prefix_pairs

    # Configure indexed directories from merged config.
    macLLM._apply_index_dirs_from_config()

    # Start periodic file index + embedding rebuild
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
