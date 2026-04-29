import pytest
from types import SimpleNamespace
from unittest.mock import Mock
from app.agent.core import AgentCore
from app.agent.session import Session
from app.capability.skill_loader import SkillLoader
from app.capability.tool_registry import tool
from app.events.event_types import EventType
from uuid import uuid4


class TestAgentCore:
    @pytest.fixture
    def mock_provider(self):
        provider = Mock()
        provider.chat.return_value = Mock(
            content="Test response",
            tool_calls=None
        )
        return provider

    @pytest.fixture
    def session(self):
        return Session("test_agent")

    def test_agent_initialization(self, mock_provider, session):
        agent = AgentCore(mock_provider, session)
        assert agent.provider == mock_provider
        assert agent.session == session

    def test_chat_simple_response(self, mock_provider, session):
        agent = AgentCore(mock_provider, session)
        response = agent.chat("Hello")

        assert response == "Test response"
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"

    def test_chat_stops_after_max_tool_rounds(self, session):
        tool_name = f"loop_probe_{uuid4().hex}"

        @tool(name=tool_name, description="Loop probe")
        def loop_probe() -> str:
            return "again"

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(
            content="",
            tool_calls=[
                {
                    "id": "call_loop",
                    "type": "function",
                    "function": {"name": tool_name, "arguments": "{}"},
                }
            ],
        )

        agent = AgentCore(provider, session, max_tool_rounds=2)
        errors = []

        def on_error(event):
            if event.session_id == session.id:
                errors.append(event)

        agent.event_bus.subscribe(EventType.ERROR, on_error)
        try:
            with pytest.raises(RuntimeError, match="maximum tool rounds"):
                agent.chat("loop")
        finally:
            agent.event_bus.unsubscribe(EventType.ERROR, on_error)

        assert provider.chat.call_count == 2
        assert errors
        assert "maximum tool rounds" in errors[0].data["message"]

    def test_chat_stream_publishes_deltas_and_saves_full_response(self, session, monkeypatch):
        provider = Mock()
        provider.chat_stream_response.return_value = iter([
            SimpleNamespace(type="content_delta", content="你"),
            SimpleNamespace(type="content_delta", content="好"),
            SimpleNamespace(
                type="message_end",
                response=SimpleNamespace(content="你好", tool_calls=None),
            ),
        ])

        agent = AgentCore(provider, session)
        published = []
        monkeypatch.setattr(agent.event_bus, "publish", published.append)

        assert list(agent.chat_stream("Hello")) == ["你", "好"]
        assert session.messages[-1] == {"role": "assistant", "content": "你好"}

        delta_events = [
            event for event in published
            if getattr(event.type, "value", None) == "message_delta"
        ]
        assert [event.data["content"] for event in delta_events] == ["你", "好"]
        assert published[-1].type == EventType.MESSAGE_SENT
        assert published[-1].data["content"] == "你好"

    def test_chat_stream_executes_tool_calls_before_streaming_final_response(self, session):
        tool_name = f"stream_probe_{uuid4().hex}"

        @tool(name=tool_name, description="Return the injected novel id")
        def stream_probe(novel_id: str = None) -> str:
            return novel_id or "missing"

        provider = Mock()
        provider.chat_stream_response.side_effect = [
            iter([
                SimpleNamespace(
                    type="message_end",
                    response=SimpleNamespace(
                        content="",
                        tool_calls=[
                            {
                                "id": "call_stream",
                                "type": "function",
                                "function": {"name": tool_name, "arguments": "{}"},
                            }
                        ],
                    ),
                )
            ]),
            iter([
                SimpleNamespace(type="content_delta", content="done"),
                SimpleNamespace(
                    type="message_end",
                    response=SimpleNamespace(content="done", tool_calls=None),
                ),
            ]),
        ]

        agent = AgentCore(provider, session, tool_context={"novel_id": "stream_ctx"})

        assert list(agent.chat_stream("run")) == ["done"]
        assert provider.chat_stream_response.call_count == 2
        assert any(
            msg["role"] == "tool" and msg["content"] == "stream_ctx"
            for msg in session.messages
        )

    def test_chat_injects_selected_skill_prompt_and_filters_tools(self, session, tmp_path):
        allowed_tool_name = f"allowed_tool_{uuid4().hex}"
        blocked_tool_name = f"blocked_tool_{uuid4().hex}"

        @tool(name=allowed_tool_name, description="Allowed by skill")
        def allowed_tool() -> str:
            return "allowed"

        @tool(name=blocked_tool_name, description="Blocked by skill")
        def blocked_tool() -> str:
            return "blocked"

        (tmp_path / "content-reviewer.md").write_text(
            f"""---
name: content-reviewer
description: 内容审查
triggers: [审查]
allowed_tools:
  - {allowed_tool_name}
priority: 5
---
# 内容审查

检查情节连贯性。
""",
            encoding="utf-8",
        )

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(provider, session, skill_loader=SkillLoader(skills_dir=tmp_path))

        assert agent.chat("请审查第一章") == "done"

        messages, tools = provider.chat.call_args.args
        assert any(
            msg["role"] == "system" and "已启用技能: content-reviewer" in msg["content"]
            for msg in messages
        )
        assert allowed_tool_name in {schema["function"]["name"] for schema in tools}
        assert blocked_tool_name not in {schema["function"]["name"] for schema in tools}
        assert all("已启用技能" not in msg["content"] for msg in session.messages)
