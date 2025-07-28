#!/usr/bin/env python3

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'macllm'))

# Mock the MacLLM class to avoid API key requirement
class MockMacLLM:
    def __init__(self, debug=False):
        self.debug = debug
        self.ui = MockUI()
    
    def debug_log(self, message, level=0):
        if self.debug:
            print(f"DEBUG: {message}")

class MockUI:
    def read_clipboard(self):
        return "test clipboard content"

# Test plugin loading
from macllm.tags.base import TagPlugin

app = MockMacLLM(debug=True)
plugins = TagPlugin.load_plugins(app)

print("Loaded plugins:")
for plugin in plugins:
    print(f"  - {plugin.__class__.__name__}: {plugin.get_prefixes()}")

# Test clipboard plugin specifically
clipboard_plugin = None
for plugin in plugins:
    if plugin.__class__.__name__ == 'ClipboardTag':
        clipboard_plugin = plugin
        break

if clipboard_plugin:
    print(f"\nClipboard plugin found: {clipboard_plugin}")
    print(f"Prefixes: {clipboard_plugin.get_prefixes()}")
    
    # Test expansion
    from macllm.core.chat_history import Conversation
    conversation = Conversation()
    result = clipboard_plugin.expand("@clipboard", conversation)
    print(f"Expansion result: {result}")
    print(f"Context history: {conversation.context_history}")
else:
    print("\nClipboard plugin NOT found!") 