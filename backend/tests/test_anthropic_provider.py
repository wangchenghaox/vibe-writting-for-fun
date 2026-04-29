from types import SimpleNamespace

from app.llm.anthropic_provider import AnthropicProvider


class FakeMessageStream:
    text_stream = ["你", "好"]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def get_final_message(self):
        return SimpleNamespace(
            content=[SimpleNamespace(type="text", text="你好")],
            stop_reason="end_turn",
        )


class FakeMessages:
    def __init__(self):
        self.stream_kwargs = None

    def stream(self, **kwargs):
        self.stream_kwargs = kwargs
        if "stream" in kwargs:
            raise TypeError("Messages.stream() got an unexpected keyword argument 'stream'")
        return FakeMessageStream()


def test_anthropic_chat_stream_response_uses_stream_helper_without_stream_flag():
    provider = AnthropicProvider(api_key="test", model="test-model", base_url="https://example.test")
    fake_messages = FakeMessages()
    provider.client = SimpleNamespace(messages=fake_messages)

    events = list(provider.chat_stream_response([{"role": "user", "content": "hello"}]))

    assert "stream" not in fake_messages.stream_kwargs
    assert [event.content for event in events if event.type == "content_delta"] == ["你", "好"]
    assert events[-1].type == "message_end"
    assert events[-1].response.content == "你好"


def test_anthropic_prepare_messages_combines_system_messages():
    provider = AnthropicProvider(api_key="test", model="test-model", base_url="https://example.test")

    system_msg, chat_messages = provider._prepare_messages([
        {"role": "system", "content": "基础规则"},
        {"role": "system", "content": "技能规则"},
        {"role": "user", "content": "hello"},
    ])

    assert system_msg == "基础规则\n\n技能规则"
    assert chat_messages == [{"role": "user", "content": "hello"}]
