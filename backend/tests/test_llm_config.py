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


def test_load_config_resolves_default_provider_from_env(tmp_path, monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "openai")
    config_path = write_llm_config(
        tmp_path,
        """
        llm:
          default: ${LLM_PROVIDER:-kimi_coding}
          providers:
            openai:
              api_key: test-openai-key
              model: gpt-test
              base_url: https://api.openai.com/v1
        """,
    )

    config = load_config(str(config_path))

    assert config["llm"]["default"] == "openai"


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
