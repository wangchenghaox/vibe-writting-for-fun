import os
import yaml
from typing import Dict, Any
from dotenv import load_dotenv
from .provider import LLMProvider, ThinkingConfig
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


def _as_bool(value: Any, default: bool = True) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _as_int(value: Any, default: int) -> int:
    if value in (None, ""):
        return default
    return int(value)


def _thinking_config(config: Dict[str, Any], provider_config: Dict[str, Any]) -> ThinkingConfig:
    merged = {
        "enabled": True,
        "effort": "medium",
        "budget_tokens": 1024,
        "keep": "all",
        "display": "omitted",
    }
    merged.update(config.get("llm", {}).get("thinking", {}) or {})
    merged.update(provider_config.get("thinking", {}) or {})

    return ThinkingConfig(
        enabled=_as_bool(merged.get("enabled"), default=True),
        effort=str(merged.get("effort") or "medium"),
        budget_tokens=_as_int(merged.get("budget_tokens"), 1024),
        keep=merged.get("keep") or None,
        display=merged.get("display") or None,
    )

def create_provider(config_path: str = "config/llm.yaml") -> LLMProvider:
    config = load_config(config_path)
    default = config['llm']['default']
    providers = config['llm']['providers']
    if default not in providers:
        raise ValueError(f"Unknown provider: {default}")

    provider_config = providers[default]
    provider_type = provider_config.get('type', default)
    timeout = float(provider_config.get('timeout', config['llm'].get('timeout', 120.0)))
    max_retries = int(provider_config.get('max_retries', config['llm'].get('max_retries', 2)))
    thinking_config = _thinking_config(config, provider_config)

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
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            thinking_config=thinking_config,
        )
    if provider_type in ('openai', 'openai_compatible'):
        return OpenAICompatibleProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            thinking_config=thinking_config,
        )
    if provider_type in ('anthropic', 'claude', 'kimi_coding'):
        return AnthropicProvider(
            api_key=api_key,
            model=model,
            base_url=base_url,
            timeout=timeout,
            max_retries=max_retries,
            thinking_config=thinking_config,
        )

    raise ValueError(f"Unknown provider type: {provider_type}")
