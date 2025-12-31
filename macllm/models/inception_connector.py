import os
import requests

class InceptionConnector:
    """Inception Labs API connector for Mercury model."""

    @classmethod
    def _get_api_key(cls):
        api_key = os.getenv("INCEPTION_API_KEY")
        if api_key is None:
            raise Exception("INCEPTION_API_KEY not found in environment variables")
        return api_key

    @classmethod
    def _generate(cls, text: str, model: str, debug_logger=None) -> tuple[str, dict]:
        api_key = cls._get_api_key()
        response = requests.post(
            'https://api.inceptionlabs.ai/v1/chat/completions',
            headers={
                'Content-Type': 'application/json',
                'Authorization': f'Bearer {api_key}'
            },
            json={
                'model': model,
                'messages': [
                    {'role': 'user', 'content': str(text)}
                ],
                'max_tokens': 1000
            }
        )
        response.raise_for_status()
        data = response.json()

        token_count = 0
        if 'usage' in data and data['usage']:
            total_tokens = data['usage'].get('total_tokens')
            if total_tokens is not None:
                token_count = total_tokens

        response_text = ""
        if 'choices' in data and len(data['choices']) > 0:
            response_text = data['choices'][0]['message']['content'] or ""

        metadata = {
            'provider': 'Inception',
            'model': model,
            'tokens': token_count
        }

        return response_text, metadata

    @classmethod
    def generate(cls, text: str, speed: str = "normal", image_path: str = None, debug_logger=None) -> tuple[str, dict]:
        if image_path:
            return None, {'provider': 'Inception', 'model': 'mercury', 'tokens': 0}
        return cls._generate(text, model="mercury", debug_logger=debug_logger)