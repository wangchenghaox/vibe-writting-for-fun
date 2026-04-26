import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv
from .provider import LLMProvider
from .openai_provider import OpenAICompatibleProvider
from .kimi import KimiProvider
from .anthropic_provider import AnthropicProvider

load_dotenv()

def resolve_env(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: resolve_env(item) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve_env(item) for item in value]
    if not isinstance(value, str) or not value.startswith('${') or not value.endswith('}'):
        return value

    expression = value[2:-1]
    if ':-' in expression:
        env_var, default_value = expression.split(':-', 1)
        return os.getenv(env_var, default_value)
    return os.getenv(expression, '')

def load_config(config_path: str = "config/llm.yaml") -> Dict[str, Any]:
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    return resolve_env(config)

def create_provider(config_path: str = "config/llm.yaml") -> LLMProvider:
    config = load_config(config_path)
    default = config['llm']['default']
    providers = config['llm']['providers']
    if default not in providers:
        raise ValueError(f"Unknown provider: {default}")

    provider_config = providers[default]
    provider_type = provider_config.get('type', default)

    api_key = provider_config['api_key']
    if not api_key:
        raise ValueError(f"API key not found for provider: {default}")
    model = provider_config.get('model')
    if not model:
        raise ValueError(f"Model not found for provider: {default}")
    base_url = provider_config.get('base_url')
    if not base_url:
        raise ValueError(f"Base URL not found for provider: {default}")

    if provider_type == 'kimi':
        return KimiProvider(
            api_key=api_key,
            model=model,
            base_url=base_url
        )
    if provider_type in ('openai', 'openai_compatible'):
        return OpenAICompatibleProvider(api_key=api_key, model=model, base_url=base_url)
    if provider_type in ('anthropic', 'claude', 'kimi_coding'):
        return AnthropicProvider(
            api_key=api_key,
            model=model,
            base_url=base_url
        )

    raise ValueError(f"Unknown provider type: {provider_type}")
