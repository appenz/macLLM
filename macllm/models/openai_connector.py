import base64
import os
import openai
from macllm.core.model_connector import ModelConnector

class OpenAIConnector(ModelConnector):
    """OpenAI API connector for GPT models."""

    def __init__(self, model, debug_logger=None):
        super().__init__(model)
        self.provider = "OpenAI"
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
                {
                    "role": "user",
                    "content": str(text)
                }
            ],
            # service_tier="priority"
            # reasoning_effort="low"
        )

        if hasattr(c, "usage") and c.usage:
            # Chat completions API usage has total/input/output tokens
            total_tokens = getattr(c.usage, "total_tokens", None)
            if total_tokens is not None:
                self.token_count = total_tokens

        # Get the response content from the first choice
        if c.choices and len(c.choices) > 0:
            return c.choices[0].message.content
        return ""
    
    def _encode_image(self, image_path: str) -> str:
        """Encode image to base64 string."""
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    def generate_with_image(self, text: str, image_path: str) -> str:
        """Generate text response with image input using OpenAI API."""
        base64_image = self._encode_image(image_path)
        if base64_image is None:
            if self.debug_logger:
                self.debug_logger("Image encoding failed.", 2)
            return None

        c = self.client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": f"{text}"},
                        {
                            "type": "input_image",
                            "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"},
                        },
                    ],
                }
            ],
        )

        if hasattr(c, "usage") and c.usage:
            total_tokens = getattr(c.usage, "total_tokens", None)
            if total_tokens is not None:
                self.token_count = total_tokens

        generated_text = getattr(c, "output_text", None)
        if self.debug_logger and generated_text is not None:
            self.debug_logger(f"Generated Text: {generated_text}")
        return generated_text