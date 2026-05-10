from types import SimpleNamespace

import anthropic
import httpx

from app.llm.anthropic_provider import AnthropicProvider
from app.llm.provider import ThinkingConfig


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


def test_anthropic_chat_sends_thinking_config_when_enabled():
    provider = AnthropicProvider(
        api_key="test",
        model="test-model",
        base_url="https://example.test",
        thinking_config=ThinkingConfig(enabled=True, budget_tokens=2048, display="omitted"),
    )

    class FakeMessages:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="ok")],
                stop_reason="end_turn",
            )

    fake_messages = FakeMessages()
    provider.client = SimpleNamespace(messages=fake_messages)

    provider.chat([{"role": "user", "content": "hi"}])

    assert fake_messages.calls[0]["thinking"] == {
        "type": "enabled",
        "budget_tokens": 2048,
        "display": "omitted",
    }


def test_anthropic_chat_sends_disabled_thinking_config_when_disabled():
    provider = AnthropicProvider(
        api_key="test",
        model="test-model",
        base_url="https://example.test",
        thinking_config=ThinkingConfig(enabled=False),
    )

    class FakeMessages:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="ok")],
                stop_reason="end_turn",
            )

    fake_messages = FakeMessages()
    provider.client = SimpleNamespace(messages=fake_messages)

    provider.chat([{"role": "user", "content": "hi"}])

    assert fake_messages.calls[0]["thinking"] == {"type": "disabled"}


def test_anthropic_response_preserves_thinking_blocks_without_mixing_into_content():
    provider = AnthropicProvider(api_key="test", model="test-model", base_url="https://example.test")
    response = provider._response_from_message(SimpleNamespace(
        content=[
            SimpleNamespace(
                type="thinking",
                thinking="内部推理",
                signature="sig-1",
                model_dump=lambda exclude_none=True: {
                    "type": "thinking",
                    "thinking": "内部推理",
                    "signature": "sig-1",
                },
            ),
            SimpleNamespace(type="text", text="公开回复"),
        ],
        stop_reason="end_turn",
    ))

    assert response.content == "公开回复"
    assert response.reasoning_blocks == [{
        "type": "thinking",
        "thinking": "内部推理",
        "signature": "sig-1",
    }]


def test_anthropic_prepare_messages_replays_reasoning_blocks_for_tool_rounds():
    provider = AnthropicProvider(api_key="test", model="test-model", base_url="https://example.test")

    _system_msg, chat_messages = provider._prepare_messages([
        {
            "role": "assistant",
            "content": "我来调用工具",
            "reasoning_blocks": [{"type": "thinking", "thinking": "内部推理", "signature": "sig-1"}],
            "tool_calls": [{
                "id": "call_1",
                "type": "function",
                "function": {"name": "read_file", "arguments": '{"path": "a.md"}'},
            }],
        },
    ])

    assert chat_messages == [{
        "role": "assistant",
        "content": [
            {"type": "thinking", "thinking": "内部推理", "signature": "sig-1"},
            {"type": "text", "text": "我来调用工具"},
            {"type": "tool_use", "id": "call_1", "name": "read_file", "input": {"path": "a.md"}},
        ],
    }]


def test_anthropic_prepare_messages_combines_system_messages():
    provider = AnthropicProvider(api_key="test", model="test-model", base_url="https://example.test")

    system_msg, chat_messages = provider._prepare_messages([
        {"role": "system", "content": "基础规则"},
        {"role": "system", "content": "技能规则"},
        {"role": "user", "content": "hello"},
    ])

    assert system_msg == "基础规则\n\n技能规则"
    assert chat_messages == [{"role": "user", "content": "hello"}]


def test_anthropic_convert_tool_enables_strict_schema_validation():
    provider = AnthropicProvider(api_key="test", model="test-model", base_url="https://example.test")

    converted = provider._convert_tool({
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write file",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
    })

    assert converted == {
        "name": "write_file",
        "description": "Write file",
        "strict": True,
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
            "additionalProperties": False,
        },
    }


def test_anthropic_chat_retries_without_strict_when_provider_rejects_it():
    provider = AnthropicProvider(api_key="test", model="test-model", base_url="https://example.test")
    request = httpx.Request("POST", "https://example.test/v1/messages")
    strict_error = anthropic.BadRequestError(
        "unexpected field: strict",
        response=httpx.Response(400, request=request),
        body={"error": {"message": "unexpected field: strict"}},
    )

    class FakeMessages:
        def __init__(self):
            self.calls = []

        def create(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise strict_error
            return SimpleNamespace(
                content=[SimpleNamespace(type="text", text="ok")],
                stop_reason="end_turn",
            )

    fake_messages = FakeMessages()
    provider.client = SimpleNamespace(messages=fake_messages)
    tools = [{
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write file",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    }]

    response = provider.chat([{"role": "user", "content": "hi"}], tools)

    assert response.content == "ok"
    assert fake_messages.calls[0]["tools"][0]["strict"] is True
    assert "strict" not in fake_messages.calls[1]["tools"][0]
