import os
from litellm import completion
from smolagents.models import LiteLLMModel

_inception_api_key = os.getenv("INCEPTION_API_KEY")
_inception_api_base = "https://api.inceptionlabs.ai/v1"
_openai_api_key = os.getenv("OPENAI_API_KEY")

def _get_provider_from_config(model_id: str, api_base: str = None) -> str:
    """Determine provider name from model configuration."""
    if api_base and "inceptionlabs" in api_base:
        return "Inception"
    if model_id.startswith("gpt-") or model_id.startswith("openai/"):
        return "OpenAI"
    if model_id.startswith("claude-") or model_id.startswith("anthropic/"):
        return "Anthropic"
    return "Unknown"

MODELS = {
    'fast': LiteLLMModel(
        model_id='openai/mercury',
        api_key=_inception_api_key,
        api_base=_inception_api_base
    ) if _inception_api_key else None,
    'normal': LiteLLMModel(
        model_id='gpt-4o',
        api_key=_openai_api_key,
        api_base='https://api.openai.com/v1'
    ) if _openai_api_key else None,
    'slow': LiteLLMModel(
        model_id='gpt-5',
        api_key=_openai_api_key,
        api_base='https://api.openai.com/v1'
    ) if _openai_api_key else None,
}

def get_model_for_speed(speed: str) -> str:
    model_obj = MODELS.get(speed.lower(), MODELS['normal'])
    if model_obj is None:
        return "unknown"
    return model_obj.model_id


def generate(messages: list[dict], speed: str = "normal", debug_logger=None) -> tuple[str, dict]:
    model_obj = MODELS.get(speed.lower(), MODELS['normal'])
    
    if model_obj is None:
        raise ValueError(f"Model for speed '{speed}' is not configured (missing API key)")
    
    kwargs = {
        'model': model_obj.model_id,
        'messages': messages
    }
    if model_obj.api_key:
        kwargs['api_key'] = model_obj.api_key
    if model_obj.api_base:
        kwargs['api_base'] = model_obj.api_base
    
    response = completion(**kwargs)
    
    response_text = response.choices[0].message.content or ""
    token_count = getattr(response.usage, "total_tokens", 0) if hasattr(response, "usage") and response.usage else 0
    
    provider = _get_provider_from_config(model_obj.model_id, model_obj.api_base)
    
    return response_text, {
        'provider': provider,
        'model': model_obj.model_id,
        'tokens': token_count
    }
