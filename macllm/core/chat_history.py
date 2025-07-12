class ChatHistory:
    def __init__(self):
        self.reset()
    
    def add_entry(self, role, text):
        if role not in ['user', 'assistant']:
            raise ValueError("Role must be either 'user' or 'assistant'")
        self.history.append((role, text))
    
    def get_history(self):
        return self.history
    
    def reset(self):
        self.history = [("assistant", "How can I help you?")] 