import base64
import os
import openai

class OpenAIConnector:
    """OpenAI API connector for GPT models."""

    @classmethod
    def _get_client(cls):
        api_key = os.getenv("OPENAI_API_KEY")
        if api_key is None:
            raise Exception("OPENAI_API_KEY not found in environment variables")
        return openai.OpenAI(api_key=api_key)

    @classmethod
    def _encode_image(cls, image_path: str) -> str:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode('utf-8')

    @classmethod
    def _get_config(cls, speed: str):
        speed = speed.lower()
        if speed == "fast":
            return {"model": "gpt-5-nano", "priority": "auto", "reasoning_effort": "minimal"}
        elif speed == "slow":
            return {"model": "gpt-5", "priority": "auto", "reasoning_effort": "medium"}
        else:
            return {"model": "gpt-5-chat-latest", "priority": "auto", "reasoning_effort": None}

    @classmethod
    def _generate(cls, text: str, model: str, priority=None, reasoning_effort=None, debug_logger=None) -> tuple[str, dict]:
        client = cls._get_client()
        extra_args = {}
        if priority is not None:
            extra_args["service_tier"] = priority
        if reasoning_effort is not None:
            extra_args["reasoning_effort"] = reasoning_effort

        c = client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": str(text)
                }
            ],
            **extra_args
        )

        token_count = 0
        if hasattr(c, "usage") and c.usage:
            total_tokens = getattr(c.usage, "total_tokens", None)
            if total_tokens is not None:
                token_count = total_tokens

        response_text = ""
        if c.choices and len(c.choices) > 0:
            response_text = c.choices[0].message.content or ""

        metadata = {
            'provider': 'OpenAI',
            'model': model,
            'tokens': token_count
        }

        return response_text, metadata

    @classmethod
    def _generate_with_image(cls, text: str, image_path: str, model: str, priority=None, reasoning_effort=None, debug_logger=None) -> tuple[str, dict]:
        client = cls._get_client()
        base64_image = cls._encode_image(image_path)
        if base64_image is None:
            if debug_logger:
                debug_logger("Image encoding failed.", 2)
            return None, {'provider': 'OpenAI', 'model': model, 'tokens': 0}

        c = client.responses.create(
            model=model,
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

        token_count = 0
        if hasattr(c, "usage") and c.usage:
            total_tokens = getattr(c.usage, "total_tokens", None)
            if total_tokens is not None:
                token_count = total_tokens

        generated_text = getattr(c, "output_text", None)
        if debug_logger and generated_text is not None:
            debug_logger(f"Generated Text: {generated_text}")

        metadata = {
            'provider': 'OpenAI',
            'model': model,
            'tokens': token_count
        }

        return generated_text, metadata

    @classmethod
    def generate(cls, text: str, speed: str = "normal", image_path: str = None, debug_logger=None) -> tuple[str, dict]:
        config = cls._get_config(speed)
        if image_path:
            return cls._generate_with_image(text, image_path, **config, debug_logger=debug_logger)
        else:
            return cls._generate(text, **config, debug_logger=debug_logger)
