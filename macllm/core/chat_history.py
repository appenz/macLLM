from typing import List, Dict, Optional, Union
from macllm import macllm


class Conversation:
    def __init__(self):
        self.agent = None
        self.agent_status = ""
        self.ui_update_callback = None
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
    
    def reset(self) -> None:
        """Clears messages and metadata, restores default welcome message."""
        self.messages = []
        self.context_history = []
        self.speed_level = "normal"
        self.agent_status = ""
        
        self.add_system_message(macllm.SYSTEM_PROMPT)
        
        self.add_assistant_message("How can I help you?")
        
        self._create_agent()
    
    def _create_agent(self, token_callback=None):
        """Create agent instance. Called lazily or on reset."""
        from macllm.core.agent_service import create_agent
        
        def status_callback(status_text: str):
            self.agent_status = status_text
            if self.ui_update_callback:
                self.ui_update_callback()
        
        self.agent = create_agent(speed=self.speed_level, status_callback=status_callback, token_callback=token_callback)


class ConversationHistory:
    def __init__(self):
        self.conversations = []

    def add_conversation(self, conversation=None):
        """Add a new Conversation object and make it the current conversation. Optionally accept an existing Conversation."""
        if conversation is None:
            conversation = Conversation()
        self.conversations.append(conversation)
        return conversation

    def get_current_conversation(self):
        """Return the most recent Conversation object, or None if none exists."""
        if self.conversations:
            return self.conversations[-1]
        return None
