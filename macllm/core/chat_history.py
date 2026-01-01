import time
import hashlib
from typing import List, Dict, Optional, Union
from macllm import macllm


def content_hash(role: str, content: str) -> str:
    """Generate stable hash for message linking."""
    return hashlib.sha256(f"{role}:{content}".encode()).hexdigest()[:16]


class Conversation:
    def __init__(self):
        self.reset()
    
    def add_user_message(self, display_content: str, expanded_content: str, context_refs: Optional[List[str]] = None) -> None:
        """Add a user message with both display and expanded content."""
        msg_hash = content_hash("user", expanded_content)
        
        message = {
            "role": "user",
            "content": expanded_content
        }
        self.messages.append(message)
        
        self.display_metadata[msg_hash] = {
            "display_content": display_content,
            "timestamp": time.time(),
            "context_refs": context_refs or []
        }
    
    def add_assistant_message(self, content: str) -> None:
        """Add an assistant message."""
        message = {
            "role": "assistant",
            "content": content
        }
        self.messages.append(message)
        
        msg_hash = content_hash("assistant", content)
        self.display_metadata[msg_hash] = {
            "display_content": content,
            "timestamp": time.time(),
            "context_refs": []
        }
    
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
    
    def get_messages_for_llm(self) -> List[Dict]:
        """Returns pure OpenAI-format messages array for LiteLLM."""
        return [
            {"role": m["role"], "content": m["content"]}
            for m in self.messages
            if m["role"] in ("system", "user", "assistant")
        ]
    
    def get_displayable_messages(self) -> List[Dict]:
        """Returns messages for UI rendering (user and assistant only)."""
        return [
            m for m in self.messages
            if m["role"] in ("user", "assistant")
        ]
    
    def get_display_content(self, message: Dict) -> str:
        """Returns original user input (before expansion) for a message."""
        msg_hash = content_hash(message["role"], message["content"])
        metadata = self.display_metadata.get(msg_hash)
        if metadata:
            return metadata["display_content"]
        return message["content"]
    
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
        self.display_metadata = {}
        self.context_history = []
        self.speed_level = "normal"
        
        self.add_system_message(macllm.SYSTEM_PROMPT)
        
        self.add_assistant_message("How can I help you?")


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
