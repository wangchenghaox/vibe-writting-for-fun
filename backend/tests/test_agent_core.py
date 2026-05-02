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

    def test_chat_returns_tool_error_to_model_when_required_argument_is_missing(self, session):
        tool_name = f"required_probe_{uuid4().hex}"

        @tool(name=tool_name, description="Require content")
        def required_probe(content: str) -> str:
            return f"saved:{content}"

        provider = Mock()
        provider.chat.side_effect = [
            SimpleNamespace(
                content="",
                tool_calls=[
                    {
                        "id": "call_missing",
                        "type": "function",
                        "function": {"name": tool_name, "arguments": "{}"},
                    }
                ],
            ),
            SimpleNamespace(content="请提供要保存的内容。", tool_calls=None),
        ]

        agent = AgentCore(provider, session)

        assert agent.chat("保存内容") == "请提供要保存的内容。"
        assert provider.chat.call_count == 2
        assert any(
            msg["role"] == "tool"
            and "missing required argument(s): content" in msg["content"]
            for msg in session.messages
        )

    def test_chat_stream_stops_repeating_identical_missing_argument_tool_error(self, session):
        tool_name = f"repeat_missing_probe_{uuid4().hex}"

        @tool(name=tool_name, description="Require content")
        def repeat_missing_probe(content: str) -> str:
            return f"saved:{content}"

        provider = Mock()
        provider.chat_stream_response.side_effect = [
            iter([
                SimpleNamespace(
                    type="message_end",
                    response=SimpleNamespace(
                        content="",
                        tool_calls=[
                            {
                                "id": "call_missing_1",
                                "type": "function",
                                "function": {"name": tool_name, "arguments": "{}"},
                            }
                        ],
                    ),
                )
            ]),
            iter([
                SimpleNamespace(
                    type="message_end",
                    response=SimpleNamespace(
                        content="我需要提供完整内容。",
                        tool_calls=[
                            {
                                "id": "call_missing_2",
                                "type": "function",
                                "function": {"name": tool_name, "arguments": "{}"},
                            }
                        ],
                    ),
                )
            ]),
            iter([
                SimpleNamespace(
                    type="message_end",
                    response=SimpleNamespace(content="should not be called", tool_calls=None),
                )
            ]),
        ]

        agent = AgentCore(provider, session)

        chunks = list(agent.chat_stream("保存第二章"))

        assert provider.chat_stream_response.call_count == 2
        assert len(chunks) == 1
        assert chunks[0].startswith(f"工具调用连续失败：{tool_name} 缺少必填参数 content。")
        assert chunks[0].endswith("请先提供完整内容，或让我先生成完整正文后再保存。")
        assert session.messages[-1] == {"role": "assistant", "content": chunks[0]}

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

    def test_chat_injects_default_chapter_writer_for_ordinal_chapter_request(self, session):
        import app.tools.file_tools  # noqa: F401

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(provider, session)

        assert agent.chat("请创作第二章") == "done"

        messages, tools = provider.chat.call_args.args
        assert any(
            msg["role"] == "system" and "已启用技能: chapter-writer" in msg["content"]
            for msg in messages
        )
        tool_names = {schema["function"]["name"] for schema in tools}
        assert "write_file" in tool_names
        assert "edit_file" in tool_names
        assert "read_file" in tool_names
        assert "save_novel_document" not in tool_names
        assert "load_novel_document" not in tool_names
        assert "save_chapter" not in tool_names

    def test_chat_injects_requirement_confirmer_before_creation_skill(self, session):
        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(provider, session)

        assert agent.chat("请设计一个主角") == "done"

        messages, _tools = provider.chat.call_args.args
        skill_prompt = next(
            msg["content"]
            for msg in messages
            if msg["role"] == "system" and "已启用技能" in msg["content"]
        )
        assert skill_prompt.index("已启用技能: requirement-confirmer") < skill_prompt.index(
            "已启用技能: character-designer"
        )

    def test_agent_filters_memory_tools_without_memory_context(self, session):
        import app.tools.memory_tools  # noqa: F401

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(provider, session)

        assert agent.chat("hi") == "done"

        _messages, tools = provider.chat.call_args.args
        tool_names = {schema["function"]["name"] for schema in tools}
        assert "remember_memory" not in tool_names
        assert "search_memory" not in tool_names
        assert "list_memories" not in tool_names
        assert "archive_memory" not in tool_names

    def test_agent_filters_memory_tools_by_default_even_with_memory_context(self, session):
        import app.tools.memory_tools  # noqa: F401

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(
            provider,
            session,
            tool_context={
                "user_id": 1,
                "novel_id": "novel_1",
                "agent_name": "main",
                "agent_instance_id": "instance_1",
            },
        )

        assert agent.chat("hi") == "done"

        _messages, tools = provider.chat.call_args.args
        tool_names = {schema["function"]["name"] for schema in tools}
        assert "remember_memory" not in tool_names
        assert "search_memory" not in tool_names
        assert "list_memories" not in tool_names
        assert "archive_memory" not in tool_names

    def test_agent_includes_memory_tools_when_enabled_with_memory_context(self, session):
        import app.tools.memory_tools  # noqa: F401

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(
            provider,
            session,
            tool_context={
                "user_id": 1,
                "novel_id": "novel_1",
                "agent_name": "main",
                "agent_instance_id": "instance_1",
            },
            memory_enabled=True,
        )

        assert agent.chat("hi") == "done"

        _messages, tools = provider.chat.call_args.args
        tool_names = {schema["function"]["name"] for schema in tools}
        assert "remember_memory" in tool_names
        assert "search_memory" in tool_names
        assert "list_memories" in tool_names
        assert "archive_memory" in tool_names

    def test_agent_includes_memory_tools_when_enabled_with_cli_user_id_zero(self, session):
        import app.tools.memory_tools  # noqa: F401

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(
            provider,
            session,
            tool_context={
                "user_id": 0,
                "novel_id": "default",
                "agent_name": "main",
                "agent_instance_id": "cli_session",
            },
            memory_enabled=True,
        )

        assert agent.chat("hi") == "done"

        _messages, tools = provider.chat.call_args.args
        tool_names = {schema["function"]["name"] for schema in tools}
        assert "remember_memory" in tool_names
        assert "search_memory" in tool_names
        assert "list_memories" in tool_names
        assert "archive_memory" in tool_names

    def test_agent_core_records_user_and_assistant_messages(self, session):
        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="回复", tool_calls=None)

        class FakeRecorder:
            def __init__(self):
                self.records = []

            def record(self, event_type, payload):
                self.records.append((event_type, payload))

        recorder = FakeRecorder()
        agent = AgentCore(provider, session, memory_recorder=recorder, memory_enabled=True)

        assert agent.chat("你好") == "回复"
        assert [event_type for event_type, payload in recorder.records] == [
            "user_message",
            "assistant_message",
        ]
        assert recorder.records[0][1]["content"] == "你好"
        assert recorder.records[1][1]["content"] == "回复"

    def test_agent_core_does_not_record_memory_events_by_default(self, session):
        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="回复", tool_calls=None)

        class FakeRecorder:
            def __init__(self):
                self.records = []

            def record(self, event_type, payload):
                self.records.append((event_type, payload))

        recorder = FakeRecorder()
        agent = AgentCore(provider, session, memory_recorder=recorder)

        assert agent.chat("你好") == "回复"
        assert recorder.records == []

    def test_agent_core_records_tool_calls_and_results(self, session):
        tool_name = f"memory_record_probe_{uuid4().hex}"

        @tool(name=tool_name, description="Probe")
        def memory_record_probe() -> str:
            return "tool result"

        provider = Mock()
        provider.chat.side_effect = [
            SimpleNamespace(
                content="",
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": tool_name, "arguments": "{}"},
                    }
                ],
            ),
            SimpleNamespace(content="done", tool_calls=None),
        ]

        class FakeRecorder:
            def __init__(self):
                self.records = []

            def record(self, event_type, payload):
                self.records.append((event_type, payload))

        recorder = FakeRecorder()
        agent = AgentCore(provider, session, memory_recorder=recorder, memory_enabled=True)

        assert agent.chat("run") == "done"
        assert [event_type for event_type, payload in recorder.records] == [
            "user_message",
            "tool_call",
            "tool_result",
            "assistant_message",
        ]
        assert recorder.records[1][1]["name"] == tool_name
        assert recorder.records[2][1]["result"] == "tool result"
