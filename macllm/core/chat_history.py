import time
from typing import List, Dict, Optional, Union


class Conversation:
    def __init__(self):
        self.reset()
    
    def add_chat_entry(self, role: str, text: str, expanded_text: str, context_refs: Optional[List[str]] = None) -> None:
        """Add a conversation turn to the chat history."""
        if role not in ['user', 'assistant']:
            raise ValueError("Role must be either 'user' or 'assistant'")
        
        entry = {
            'role': role,
            'text': text,
            'expanded_text': expanded_text,
            'timestamp': time.time(),
            'context_refs': context_refs or []
        }
        self.chat_history.append(entry)
    
    def add_context(self, suggested_name: str, source: str, context_type: str, context: Union[str, bytes], icon = None) -> str:
        """Add context entry, returns the actual name used. Avoids duplicates based on source."""
        # Check if source already exists
        for ctx in self.context_history:
            if ctx['source'] == source:
                return ctx['name']
        
        # Generate unique name if suggested_name already exists
        actual_name = suggested_name
        counter = 1
        
        while any(ctx['name'] == actual_name for ctx in self.context_history):
            actual_name = f"{suggested_name}-{counter}"
            counter += 1
        
        print("Icon: ", icon)
        if icon is None:
            icon = ""

        # Add new context entry
        entry = {
            'name': actual_name,
            'source': source,
            'type': context_type,
            'context': context,
            'icon': icon
        }
        self.context_history.append(entry)
        return actual_name
    
    role_icons = {
        'user': 'User: ',
        'assistant': 'Assistant: ',
        'system': 'System: ',
    }

    def get_chat_history_original(self) -> str:
        """Returns the unexpanded chat history to show the user as a string."""
        formatted_history = []
        for entry in self.chat_history:
            role = entry['role']
            text = entry['text']
            formatted_history.append(f"{self.role_icons[role]} {text}")
        return "\n\n".join(formatted_history)
    
    def get_chat_history_expanded(self) -> str:
        """Returns the fully expanded chat history for the LLM as a string."""
        formatted_history = []
        for entry in self.chat_history:
            role = entry['role'].capitalize()
            expanded_text = entry['expanded_text']
            formatted_history.append(f"{role}: {expanded_text}")
        return "\n".join(formatted_history)
    
    def get_context_history_text(self) -> str:
        """Returns context history as one large string (excluding images)."""
        text_parts = []
        for ctx in self.context_history:
            if ctx['type'] != 'image':
                context_name = ctx['name']
                text_parts.append(
                    f"--- contents:{context_name} ---\n"
                    f"{ctx['context']}\n"
                    f"--- end contents:{context_name} ---\n"
                )
        return "\n".join(text_parts)
    
    def get_context_last_image(self) -> Optional[bytes]:
        """Returns only the last image in the context history."""
        for ctx in reversed(self.context_history):
            if ctx['type'] == 'image':
                return ctx['context']
        return None
    
    def reset(self) -> None:
        """Clears both lists, restores default message."""
        self.chat_history = []
        self.context_history = []
        # Add default welcome message
        self.add_chat_entry(
            role="assistant",
            text="How can I help you?",
            expanded_text="How can I help you?",
            context_refs=[]
        ) 


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