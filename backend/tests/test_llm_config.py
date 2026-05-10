from textwrap import dedent

from app.llm.config import create_provider, load_config


def write_llm_config(tmp_path, content: str):
    config_path = tmp_path / "llm.yaml"
    config_path.write_text(dedent(content), encoding="utf-8")
    return config_path


def test_create_provider_supports_openai_mode(tmp_path):
    config_path = write_llm_config(
        tmp_path,
        """
        llm:
          default: openai
          providers:
            openai:
              api_key: test-openai-key
              model: gpt-test
              base_url: https://api.openai.com/v1
        """,
    )

    provider = create_provider(str(config_path))

    assert provider.__class__.__name__ == "OpenAICompatibleProvider"
    assert provider.model == "gpt-test"
    assert provider.timeout == 120.0


def test_create_provider_supports_claude_mode(tmp_path):
    config_path = write_llm_config(
        tmp_path,
        """
        llm:
          default: claude
          providers:
            claude:
              api_key: test-anthropic-key
              model: claude-test
              base_url: https://api.anthropic.com
        """,
    )

    provider = create_provider(str(config_path))

    assert provider.__class__.__name__ == "AnthropicProvider"
    assert provider.model == "claude-test"
    assert provider.timeout == 120.0


def test_create_provider_uses_configured_timeout_and_retries(tmp_path):
    config_path = write_llm_config(
        tmp_path,
        """
        llm:
          default: kimi_coding
          timeout: 240
          max_retries: 4
          providers:
            kimi_coding:
              type: kimi_coding
              api_key: test-kimi-key
              model: kimi-test
              base_url: https://api.kimi.com/coding/
        """,
    )

    provider = create_provider(str(config_path))

    assert provider.__class__.__name__ == "AnthropicProvider"
    assert provider.timeout == 240.0
    assert provider.max_retries == 4


def test_create_provider_enables_thinking_by_default(tmp_path):
    config_path = write_llm_config(
        tmp_path,
        """
        llm:
          default: openai
          providers:
            openai:
              api_key: test-openai-key
              model: gpt-test
              base_url: https://api.openai.com/v1
        """,
    )

    provider = create_provider(str(config_path))

    assert provider.thinking_config.enabled is True
    assert provider.thinking_config.effort == "medium"
    assert provider.thinking_config.budget_tokens == 1024


def test_create_provider_allows_provider_thinking_override(tmp_path):
    config_path = write_llm_config(
        tmp_path,
        """
        llm:
          default: claude
          thinking:
            enabled: true
            effort: medium
            budget_tokens: 1024
          providers:
            claude:
              api_key: test-anthropic-key
              model: claude-test
              base_url: https://api.anthropic.com
              thinking:
                enabled: false
                effort: high
                budget_tokens: 2048
        """,
    )

    provider = create_provider(str(config_path))

    assert provider.thinking_config.enabled is False
    assert provider.thinking_config.effort == "high"
    assert provider.thinking_config.budget_tokens == 2048


def test_load_config_resolves_default_provider_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    config_path = write_llm_config(
        tmp_path,
        """
        llm:
          default: ${LLM_PROVIDER:-kimi}
          providers:
            openai:
              api_key: test-openai-key
              model: gpt-test
              base_url: https://api.openai.com/v1
        """,
    )

    config = load_config(str(config_path))

    assert config["llm"]["default"] == "openai"


def test_default_config_uses_latest_kimi_model_when_env_unset(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.delenv("KIMI_MODEL", raising=False)

    config = load_config("config/llm.yaml")

    assert config["llm"]["default"] == "kimi"
    assert config["llm"]["providers"]["kimi"]["model"] == "kimi-k2.6"


def test_default_config_declares_openai_and_claude_modes():
    config = load_config("config/llm.yaml")

    assert "openai" in config["llm"]["providers"]
    assert "claude" in config["llm"]["providers"]


def test_default_config_resolves_kimi_models_from_env(monkeypatch):
    monkeypatch.setenv("KIMI_MODEL", "moonshot-test-model")
    monkeypatch.setenv("KIMI_CODING_MODEL", "kimi-coding-test-model")

    config = load_config("config/llm.yaml")

    assert config["llm"]["providers"]["kimi"]["model"] == "moonshot-test-model"
    assert config["llm"]["providers"]["kimi_coding"]["model"] == "kimi-coding-test-model"


def test_default_config_declares_thinking_enabled_by_default(monkeypatch):
    monkeypatch.delenv("LLM_THINKING_ENABLED", raising=False)
    monkeypatch.delenv("LLM_THINKING_EFFORT", raising=False)
    monkeypatch.delenv("LLM_THINKING_BUDGET_TOKENS", raising=False)

    config = load_config("config/llm.yaml")

    assert config["llm"]["thinking"]["enabled"] == "true"
    assert config["llm"]["thinking"]["effort"] == "medium"
    assert config["llm"]["thinking"]["budget_tokens"] == "1024"
