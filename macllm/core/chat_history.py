import os
from typing import List, Dict, Optional, Union


class Conversation:
    def __init__(self):
        self.agent = None
        self.agent_cls = None  # set lazily in reset() or by caller
        self.ui_update_callback = None
        self.title = "New Agent"
        self.reset()
    
    def add_user_message(self, content: str) -> None:
        """Add a user message (display text only)."""
        message = {
            "role": "user",
            "content": content
        }
        self.messages.append(message)
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message."""
        message = {
            "role": "assistant",
            "content": content
        }
        self.messages.append(message)
    
    def add_system_message(self, content: str) -> None:
        """Add or update system message (typically only at conversation start)."""
        if self.messages and self.messages[0]["role"] == "system":
            self.messages[0]["content"] = content
        else:
            message = {
                "role": "system",
                "content": content
            }
            self.messages.insert(0, message)
    
    def get_displayable_messages(self) -> List[Dict]:
        """Returns messages for UI rendering (user and assistant only)."""
        return [
            m for m in self.messages
            if m["role"] in ("user", "assistant")
        ]
    
    def add_context(self, suggested_name: str, source: str, context_type: str, context: Union[str, bytes], icon = None) -> str:
        """Add context entry, returns the actual name used. Avoids duplicates based on source."""
        for ctx in self.context_history:
            if ctx['source'] == source:
                return ctx['name']
        
        actual_name = suggested_name
        counter = 1
        
        while any(ctx['name'] == actual_name for ctx in self.context_history):
            actual_name = f"{suggested_name}-{counter}"
            counter += 1
        
        if icon is None:
            icon = ""

        entry = {
            'name': actual_name,
            'source': source,
            'type': context_type,
            'context': context,
            'icon': icon
        }
        self.context_history.append(entry)
        return actual_name

    def has_path_in_context(self, path: str) -> bool:
        """Check if a file path was explicitly referenced in this conversation's context."""
        for ctx in self.context_history:
            if ctx.get("type") == "path" and ctx.get("source") == path:
                return True
        return False
    
    def _get_agent_cls(self):
        if self.agent_cls is None:
            from macllm.agents import get_default_agent_class
            self.agent_cls = get_default_agent_class()
        return self.agent_cls

    def grant_directory(self, path: str) -> None:
        """Add a directory to the sandbox grant list for this conversation."""
        abs_path = os.path.abspath(os.path.expanduser(path))
        if abs_path not in self.granted_dirs:
            self.granted_dirs.append(abs_path)

    def get_granted_dirs(self) -> list[str]:
        """Return all granted directories (config defaults + conversation grants)."""
        from macllm.core.config import get_runtime_config

        config = get_runtime_config()
        config_dirs = [
            os.path.abspath(os.path.expanduser(d))
            for d in config.shell.default_dirs
        ]
        return list(dict.fromkeys(config_dirs + self.granted_dirs))

    def reset(self, clear_persisted: bool = False) -> None:
        """Clears messages and metadata, restores default welcome message."""
        self.messages = []
        self.context_history = []
        self.granted_dirs: list[str] = []
        self.speed_level = "normal"
        self.title = "New Agent"

        self._get_agent_cls()
        
        if self.agent is not None:
            self.agent.memory.steps = []
        self._create_agent()
        
        if clear_persisted:
            from macllm.core.memory import clear_conversation
            clear_conversation()
    
    def _create_agent(self, token_callback=None):
        """Create agent instance using the current agent class.

        Routes through :func:`agent_service.create_agent` so tests can
        monkeypatch a single function to inject mock agents.
        """
        from macllm.core.agent_service import create_agent

        old_steps = None
        if self.agent is not None:
            old_steps = self.agent.memory.steps
        
        self.agent = create_agent(
            agent_cls=self._get_agent_cls(),
            speed=self.speed_level,
            token_callback=token_callback,
        )
        
        if old_steps is not None:
            self.agent.memory.steps = old_steps


class ConversationHistory:
    def __init__(self):
        self.conversations = []
        self.active_index = -1

    def add_conversation(self, conversation=None):
        """Add a new Conversation object and make it the current (active) conversation."""
        if conversation is None:
            conversation = Conversation()
        self.conversations.append(conversation)
        self.active_index = len(self.conversations) - 1
        return conversation

    def get_current_conversation(self):
        """Return the active Conversation object, or None if none exists."""
        if self.conversations and 0 <= self.active_index < len(self.conversations):
            return self.conversations[self.active_index]
        return None

    def set_active(self, index: int) -> bool:
        """Switch the active conversation by index. Returns True on success."""
        if 0 <= index < len(self.conversations):
            self.active_index = index
            return True
        return False

    def cycle(self, delta: int) -> bool:
        """Move active index by delta (clamped to bounds). Returns True if changed."""
        if not self.conversations:
            return False
        new_index = max(0, min(len(self.conversations) - 1, self.active_index + delta))
        if new_index == self.active_index:
            return False
        self.active_index = new_index
        return True

    def remove_conversation(self, index: int) -> bool:
        """Remove conversation at *index*, ensuring at least one always exists."""
        if index < 0 or index >= len(self.conversations):
            return False
        self.conversations.pop(index)
        if not self.conversations:
            self.add_conversation()
            return True
        if index < self.active_index:
            self.active_index -= 1
        elif index == self.active_index:
            self.active_index = min(self.active_index, len(self.conversations) - 1)
        return True
