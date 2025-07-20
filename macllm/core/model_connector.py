class ModelConnector:
    """Base class for model connectors that handle LLM interactions."""
    
    def __init__(self, model: str):
        self.provider = "Unknown"
        self.model = model
        self.context_limit = 10000
        self.token_count = 0
    
    def generate(self, text: str) -> str:
        """Generate text response from the model."""
        pass
    
    def generate_with_image(self, text: str, image_path: str) -> str:
        """Generate text response from the model with image input."""
        pass 
    
    def get_token_count(self) -> int:
        """Get the number of tokens used in the last generation."""
        return self.token_count
    
    def get_provider_model(self) -> tuple[str, str]:
        """Get the provider and model name."""
        return self.provider, self.model