import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv
from .provider import LLMProvider
from .kimi import KimiProvider
from .anthropic_provider import AnthropicProvider

load_dotenv()

def load_config(config_path: str = "config/llm.yaml") -> Dict[str, Any]:
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)

    for provider_name, provider_config in config['llm']['providers'].items():
        for key, value in provider_config.items():
            if isinstance(value, str) and value.startswith('${') and value.endswith('}'):
                env_var = value[2:-1]
                provider_config[key] = os.getenv(env_var, '')

    return config

def create_provider(config_path: str = "config/llm.yaml") -> LLMProvider:
    config = load_config(config_path)
    default = config['llm']['default']
    provider_config = config['llm']['providers'][default]

    api_key = provider_config['api_key']
    if not api_key:
        raise ValueError(f"API key not found for provider: {default}")

    if default == 'kimi':
        return KimiProvider(
            api_key=api_key,
            model=provider_config['model'],
            base_url=provider_config['base_url']
        )
    elif default == 'kimi_coding':
        return AnthropicProvider(
            api_key=api_key,
            model=provider_config['model'],
            base_url=provider_config['base_url']
        )

    raise ValueError(f"Unknown provider: {default}")
