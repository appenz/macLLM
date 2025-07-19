import base64
import requests
import os
import openai
from macllm.core.model_connector import ModelConnector

class OpenAIConnector(ModelConnector):
    """OpenAI API connector for GPT models."""
    
    def __init__(self, model: str, temperature: float = 0.0, debug_logger=None):
        super().__init__(model, temperature)
        self.openai_api_key = os.getenv("OPENAI_API_KEY")
        if self.openai_api_key is None:
            raise Exception("OPENAI_API_KEY not found in environment variables")
        self.client = openai.OpenAI(api_key=self.openai_api_key)
        self.debug_logger = debug_logger

    def generate(self, text: str) -> str:
        """Generate text response using OpenAI API."""
        c = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "user", "content": str(text)},
            ],
            temperature=self.temperature,
        )
        return c.choices[0].message.content
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def generate_with_image(self, text: str, image_path: str) -> str:
        """Generate text response with image input using OpenAI API."""
        # Getting the base64 string
        base64_image = self._encode_image(image_path)
        if base64_image is None:
            print(f'Image encoding failed.')

        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_api_key}"
        }

        payload = {
            "model": "gpt-4o",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"{text}"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                            }
                        }
                    ]
                }
            ],
            "max_tokens": 1000
        }

        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

        # Extract the content from the response
        if response.status_code == 200:
            response_data = response.json()
            if 'choices' in response_data and len(response_data['choices']) > 0:
                generated_text = response_data['choices'][0]['message']['content']
                if self.debug_logger:
                    self.debug_logger(f'Generated Text: {generated_text}')
                return generated_text
            else:
                if self.debug_logger:
                    self.debug_logger('No generated content found.', 2)
                return None
        else:
            if self.debug_logger:
                self.debug_logger(f'Failed to generate content. Status Code: {response.status_code}', 2)
                self.debug_logger(f'Response: {response.json()}', 2)
            return None 