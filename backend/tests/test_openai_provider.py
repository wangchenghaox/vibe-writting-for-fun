from types import SimpleNamespace

from app.llm.kimi import KimiProvider
from app.llm.openai_provider import OpenAICompatibleProvider
from app.llm.provider import ThinkingConfig


class FakeCompletions:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


def completion(message, finish_reason="stop"):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=message, finish_reason=finish_reason)]
    )


def test_openai_provider_sends_reasoning_effort_when_thinking_enabled():
    provider = OpenAICompatibleProvider(
        api_key="test",
        model="gpt-test",
        base_url="https://example.test/v1",
        thinking_config=ThinkingConfig(enabled=True, effort="high"),
    )
    fake_completions = FakeCompletions(completion(SimpleNamespace(content="ok", tool_calls=None)))
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))

    response = provider.chat([{"role": "user", "content": "hi"}])

    assert response.content == "ok"
    assert fake_completions.calls[0]["reasoning_effort"] == "high"


def test_openai_provider_sends_none_reasoning_effort_when_thinking_disabled():
    provider = OpenAICompatibleProvider(
        api_key="test",
        model="gpt-test",
        base_url="https://example.test/v1",
        thinking_config=ThinkingConfig(enabled=False, effort="medium"),
    )
    fake_completions = FakeCompletions(completion(SimpleNamespace(content="ok", tool_calls=None)))
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))

    provider.chat([{"role": "user", "content": "hi"}])

    assert fake_completions.calls[0]["reasoning_effort"] == "none"


def test_openai_provider_strips_vendor_reasoning_fields_from_standard_requests():
    provider = OpenAICompatibleProvider(
        api_key="test",
        model="gpt-test",
        base_url="https://example.test/v1",
    )
    fake_completions = FakeCompletions(completion(SimpleNamespace(content="ok", tool_calls=None)))
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))

    provider.chat([
        {"role": "assistant", "content": "ok", "reasoning_content": "internal"},
        {"role": "user", "content": "next"},
    ])

    assert "reasoning_content" not in fake_completions.calls[0]["messages"][0]


def test_kimi_provider_uses_extra_body_thinking_and_preserves_reasoning_content():
    provider = KimiProvider(
        api_key="test",
        model="kimi-test",
        base_url="https://example.test/v1",
        thinking_config=ThinkingConfig(enabled=True, keep="all"),
    )
    message = SimpleNamespace(
        content="ok",
        tool_calls=None,
        reasoning_content="模型推理",
    )
    fake_completions = FakeCompletions(completion(message))
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))

    response = provider.chat([
        {"role": "assistant", "content": "old", "reasoning_content": "历史推理"},
        {"role": "user", "content": "next"},
    ])

    assert fake_completions.calls[0]["extra_body"] == {
        "thinking": {"type": "enabled", "keep": "all"}
    }
    assert fake_completions.calls[0]["messages"][0]["reasoning_content"] == "历史推理"
    assert response.reasoning_content == "模型推理"


def test_kimi_provider_can_disable_thinking_with_extra_body():
    provider = KimiProvider(
        api_key="test",
        model="kimi-test",
        base_url="https://example.test/v1",
        thinking_config=ThinkingConfig(enabled=False),
    )
    fake_completions = FakeCompletions(completion(SimpleNamespace(content="ok", tool_calls=None)))
    provider.client = SimpleNamespace(chat=SimpleNamespace(completions=fake_completions))

    provider.chat([{"role": "user", "content": "hi"}])

    assert fake_completions.calls[0]["extra_body"] == {"thinking": {"type": "disabled"}}
