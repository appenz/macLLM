class ModelConnector:
    """Base class for model connectors that handle LLM interactions."""
    
    def __init__(self, model: str, temperature: float = 0.0):
        self.model = model
        self.temperature = temperature
        self.context_limit = 10000
    
    def generate(self, text: str) -> str:
        """Generate text response from the model."""
        pass
    
    def generate_with_image(self, text: str, image_path: str) -> str:
        """Generate text response from the model with image input."""
        pass 