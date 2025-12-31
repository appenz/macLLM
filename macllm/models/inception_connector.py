import os
import requests
from macllm.core.model_connector import ModelConnector

class InceptionConnector(ModelConnector):
    """Inception Labs API connector for Mercury model."""

    def __init__(self, model, priority=None, reasoning_effort=None, debug_logger=None):
        super().__init__(model)
        self.provider = "Inception"
        self.api_key = os.getenv("INCEPTION_API_KEY")
        if self.api_key is None:
            raise Exception("INCEPTION_API_KEY not found in environment variables")
        self.debug_logger = debug_logger
        self.priority = priority
        self.reasoning_effort = reasoning_effort

    def generate(self, text: str) -> str:
        """Generate text response using Inception Labs API."""
        response = requests.post(
            'https://api.inceptionlabs.ai/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {self.api_key}'
            },
            json={
                'model': self.model,
                'messages': [
                    {'role': 'user', 'content': str(text)}
                ],
                'max_tokens': 1000
            }
        )
        response.raise_for_status()
        data = response.json()

        if 'usage' in data and data['usage']:
            total_tokens = data['usage'].get('total_tokens')
            if total_tokens is not None:
                self.token_count = total_tokens

        if 'choices' in data and len(data['choices']) > 0:
            return data['choices'][0]['message']['content']
        return ""

    def generate_with_image(self, text: str, image_path: str) -> str:
        """Generate text response with image input using Inception Labs API."""
        return None

