import os
import litellm
from litellm import completion
from smolagents.models import LiteLLMModel
from macllm.core.config import get_runtime_config


def enable_litellm_debug():
    """Enable LiteLLM debug logging for troubleshooting API calls."""
    litellm._turn_on_debug()

_inception_api_base = "https://api.inceptionlabs.ai/v1"

def _get_provider_from_config(model_id: str, api_base: str = None) -> str:
    """Determine provider name from model configuration."""
    if api_base and "inceptionlabs" in api_base:
        return "Inception"
    if model_id.startswith("gpt-") or model_id.startswith("openai/"):
        return "OpenAI"
    if model_id.startswith("claude-") or model_id.startswith("anthropic/"):
        return "Anthropic"
    if model_id.startswith("gemini/"):
        return "Gemini"
    return "Unknown"

MODELS = {
    'fast': None,
    'normal': None,
    'slow': None,
}


def _fallback_env_keys() -> dict[str, str]:
    return {
        "inception": os.getenv("INCEPTION_API_KEY", ""),
        "openai": os.getenv("OPENAI_API_KEY", ""),
        "gemini": os.getenv("GEMINI_API_KEY", ""),
    }


def refresh_models():
    cfg = get_runtime_config()
    env = _fallback_env_keys()
    inception_key = cfg.api_keys.inception or env["inception"]
    openai_key = cfg.api_keys.openai or env["openai"]
    gemini_key = cfg.api_keys.gemini or env["gemini"]

    MODELS['fast'] = (
        LiteLLMModel(
            model_id='openai/mercury',
            api_key=inception_key,
            api_base=_inception_api_base
        ) if inception_key else None
    )
    MODELS['normal'] = (
        LiteLLMModel(
            model_id='gemini/gemini-3-flash-preview',
            api_key=gemini_key,
        ) if gemini_key else None
    )
    MODELS['slow'] = (
        LiteLLMModel(
            model_id='gpt-5.4',
            api_key=openai_key,
            api_base='https://api.openai.com/v1'
        ) if openai_key else None
    )


refresh_models()

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
