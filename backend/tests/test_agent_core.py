import json
import pytest
from types import SimpleNamespace
from unittest.mock import Mock
from app.agent.core import AgentCore
from app.agent.session import Session
from app.capability.skill_loader import SkillLoader
from app.capability.tool_registry import tool
from app.events.event_types import EventType
from app.llm.provider import Response
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
        assert agent.max_tool_rounds == 20

    def test_chat_simple_response(self, mock_provider, session):
        agent = AgentCore(mock_provider, session)
        response = agent.chat("Hello")

        assert response == "Test response"
        assert len(session.messages) == 2
        assert session.messages[0]["role"] == "user"
        assert session.messages[1]["role"] == "assistant"

    def test_chat_injects_base_system_prompt_before_skill_catalog(self, session, tmp_path):
        (tmp_path / "chapter-writer.md").write_text(
            """---
name: chapter-writer
description: 章节创作
triggers: [写章节]
priority: 5
---
# 章节创作
""",
            encoding="utf-8",
        )

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(provider, session, skill_loader=SkillLoader(skills_dir=tmp_path))

        assert agent.chat("普通闲聊") == "done"

        messages, _tools = provider.chat.call_args.args
        system_messages = [msg["content"] for msg in messages if msg["role"] == "system"]
        assert "你是一个中文长篇小说创作 CLI Agent" in system_messages[0]
        assert "核心职责是和用户一起完成小说创作、规划、审稿、资料整理和文件落盘工作" in system_messages[0]
        assert "默认使用中文回复" in system_messages[0]
        assert "不要假装已经读取文件" in system_messages[0]
        assert "正式开始写作、整理、改写、审稿或保存前" in system_messages[0]
        assert "progress.md" in system_messages[0]
        assert "修改或生成新内容后" in system_messages[0]
        assert "技能: chapter-writer" in system_messages[1]
        assert all(
            "中文长篇小说创作 CLI Agent" not in msg["content"]
            for msg in session.messages
        )

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

    def test_chat_stream_reports_and_saves_partial_content_when_stream_breaks(self, session):
        def broken_stream(*args, **kwargs):
            yield SimpleNamespace(type="content_delta", content="前半段")
            raise TimeoutError("stream timed out")

        provider = Mock()
        provider.chat_stream_response.side_effect = broken_stream
        agent = AgentCore(provider, session)
        errors = []

        def on_error(event):
            if event.session_id == session.id:
                errors.append(event)

        agent.event_bus.subscribe(EventType.ERROR, on_error)
        try:
            chunks = list(agent.chat_stream("写一段"))
        finally:
            agent.event_bus.unsubscribe(EventType.ERROR, on_error)

        assert chunks == ["前半段", "\n\n[流式输出中断：TimeoutError: stream timed out]"]
        assert session.messages[-1] == {
            "role": "assistant",
            "content": "前半段\n\n[流式输出中断：TimeoutError: stream timed out]",
        }
        assert errors
        assert errors[0].data["message"] == "流式输出中断：TimeoutError: stream timed out"

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

    def test_chat_intercepts_write_file_without_content_before_visible_tool_error(self, session):
        import app.tools.file_tools  # noqa: F401

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(
            content="我来保存第五卷大纲到文件中。",
            tool_calls=[
                {
                    "id": "call_missing_content",
                    "type": "function",
                    "function": {
                        "name": "write_file",
                        "arguments": '{"path": "novels/abandoned_author/outlines/volume_05.md"}',
                    },
                }
            ],
        )

        agent = AgentCore(provider, session)
        tool_events = []

        def on_tool_called(event):
            if event.session_id == session.id:
                tool_events.append(event)

        agent.event_bus.subscribe(EventType.TOOL_CALLED, on_tool_called)
        try:
            response = agent.chat("保存第五卷大纲")
        finally:
            agent.event_bus.unsubscribe(EventType.TOOL_CALLED, on_tool_called)

        assert provider.chat.call_count == 1
        assert tool_events == []
        assert "无法保存到 novels/abandoned_author/outlines/volume_05.md" in response
        assert "缺少要写入的完整内容" in response
        assert session.messages[-2] == {
            "role": "tool",
            "content": "Tool write_file missing required argument(s): content",
            "tool_call_id": "call_missing_content",
            "name": "write_file",
        }
        assert session.messages[-1] == {"role": "assistant", "content": response}

    def test_chat_backfills_write_file_content_from_previous_assistant_draft(
        self,
        session,
        monkeypatch,
        tmp_path,
    ):
        import app.tools.file_tools  # noqa: F401
        from app.core.config import settings

        sandbox = tmp_path / "sandbox"
        sandbox.mkdir()
        monkeypatch.setattr(settings, "WORKDIR", sandbox)

        draft = "# 第五卷章级细纲\n\n## 第一章\n\n完整正文。"
        session.add_message("user", "重新生成第五卷细纲")
        session.add_message("assistant", draft)

        provider = Mock()
        provider.chat.side_effect = [
            SimpleNamespace(
                content="我直接在回复中生成第五卷完整内容并保存。",
                tool_calls=[
                    {
                        "id": "call_save_previous_draft",
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "arguments": '{"path": "abandoned_author/outlines/volume_05.md"}',
                        },
                    }
                ],
            ),
            SimpleNamespace(content="已保存第五卷细纲。", tool_calls=None),
        ]

        agent = AgentCore(provider, session)

        assert agent.chat("保存第五卷细纲") == "已保存第五卷细纲。"
        assert provider.chat.call_count == 2
        assert (
            sandbox / "abandoned_author" / "outlines" / "volume_05.md"
        ).read_text(encoding="utf-8") == draft
        assert any(
            msg["role"] == "tool"
            and msg["tool_call_id"] == "call_save_previous_draft"
            and "已写入文件" in msg["content"]
            for msg in session.messages
        )
        stored_tool_call = next(
            msg["tool_calls"][0]
            for msg in session.messages
            if msg.get("tool_calls")
            and msg["tool_calls"][0]["id"] == "call_save_previous_draft"
        )
        assert json.loads(stored_tool_call["function"]["arguments"])["content"] == draft

    def test_chat_records_tool_result_when_tool_execution_raises(self, session):
        tool_name = f"raising_probe_{uuid4().hex}"

        @tool(name=tool_name, description="Always raises")
        def raising_probe() -> str:
            raise TypeError("boom")

        provider = Mock()
        provider.chat.side_effect = [
            SimpleNamespace(
                content="",
                tool_calls=[
                    {
                        "id": "call_raises",
                        "type": "function",
                        "function": {"name": tool_name, "arguments": "{}"},
                    }
                ],
            ),
            SimpleNamespace(content="已处理错误。", tool_calls=None),
        ]

        agent = AgentCore(provider, session)

        assert agent.chat("run") == "已处理错误。"
        assert provider.chat.call_count == 2
        assert any(
            msg["role"] == "tool"
            and msg["tool_call_id"] == "call_raises"
            and msg["name"] == tool_name
            and msg["content"] == f"Tool {tool_name} failed: TypeError: boom"
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

    def test_chat_does_not_auto_trigger_skill_prompt_or_filter_tools(self, session, tmp_path):
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
        assert all(
            "已启用技能" not in msg["content"]
            for msg in messages
            if msg["role"] == "system"
        )
        assert allowed_tool_name in {schema["function"]["name"] for schema in tools}
        assert blocked_tool_name in {schema["function"]["name"] for schema in tools}
        assert all("已启用技能" not in msg["content"] for msg in session.messages)

    def test_chat_injects_skill_catalog_prompt_even_without_selected_skill(self, session, tmp_path):
        (tmp_path / "chapter-writer.md").write_text(
            """---
name: chapter-writer
description: 章节创作
triggers: [写章节]
allowed_tools: [read_file]
priority: 5
---
# 章节创作
""",
            encoding="utf-8",
        )
        (tmp_path / "content-reviewer.md").write_text(
            """---
name: content-reviewer
description: 内容审查
triggers: [审查]
allowed_tools: [read_file]
priority: 1
---
# 内容审查
""",
            encoding="utf-8",
        )

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(provider, session, skill_loader=SkillLoader(skills_dir=tmp_path))

        assert agent.chat("普通闲聊") == "done"

        messages, _tools = provider.chat.call_args.args
        catalog_prompt = next(
            msg["content"]
            for msg in messages
            if msg["role"] == "system" and "你可以使用以下本地创作技能" in msg["content"]
        )
        assert "技能: chapter-writer" in catalog_prompt
        assert "说明: 章节创作" in catalog_prompt
        assert "触发时机:\n- 写章节" in catalog_prompt
        assert "说明文件: skills/chapter-writer.md" in catalog_prompt
        assert "技能: content-reviewer" in catalog_prompt
        assert "可用工具" not in catalog_prompt
        assert "`read_file`" not in catalog_prompt
        assert all(
            "你可以使用以下本地创作技能" not in msg["content"]
            for msg in session.messages
        )

    def test_chat_does_not_publish_skill_trigger_notification(self, session, tmp_path, monkeypatch):
        (tmp_path / "chapter-writer.md").write_text(
            """---
name: chapter-writer
description: 章节创作
triggers: [写章节]
priority: 5
---
# 章节创作
""",
            encoding="utf-8",
        )

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(provider, session, skill_loader=SkillLoader(skills_dir=tmp_path))
        published = []
        monkeypatch.setattr(agent.event_bus, "publish", published.append)

        assert agent.chat("请写章节") == "done"

        assert all(getattr(event.type, "value", None) != "skill_triggered" for event in published)

    def test_chat_injects_catalog_but_not_default_chapter_writer_for_ordinal_request(self, session):
        import app.tools.file_tools  # noqa: F401

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(provider, session)

        assert agent.chat("请创作第二章") == "done"

        messages, tools = provider.chat.call_args.args
        assert any(
            msg["role"] == "system" and "技能: chapter-writer" in msg["content"]
            for msg in messages
        )
        assert all(
            "已启用技能" not in msg["content"]
            for msg in messages
            if msg["role"] == "system"
        )
        tool_names = {schema["function"]["name"] for schema in tools}
        assert "write_file" in tool_names
        assert "edit_file" in tool_names
        assert "read_file" in tool_names

    def test_agent_injects_write_file_usage_rule_when_available(self, session):
        import app.tools.file_tools  # noqa: F401

        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(provider, session)

        assert agent.chat("请创作第二章并保存") == "done"

        messages, tools = provider.chat.call_args.args
        assert "write_file" in {schema["function"]["name"] for schema in tools}
        assert any(
            msg["role"] == "system"
            and "调用 write_file 必须同时提供 path 和完整 content" in msg["content"]
            and "没有完整正文时不要调用 write_file" in msg["content"]
            for msg in messages
        )

    def test_chat_does_not_auto_inject_requirement_confirmer_before_creation_skill(self, session):
        provider = Mock()
        provider.chat.return_value = SimpleNamespace(content="done", tool_calls=None)
        agent = AgentCore(provider, session)

        assert agent.chat("请设计一个主角") == "done"

        messages, _tools = provider.chat.call_args.args
        catalog_prompt = next(
            msg["content"]
            for msg in messages
            if msg["role"] == "system" and "你可以使用以下本地创作技能" in msg["content"]
        )
        assert "技能: requirement-confirmer" in catalog_prompt
        assert "技能: character-designer" in catalog_prompt
        assert all(
            "已启用技能" not in msg["content"]
            for msg in messages
            if msg["role"] == "system"
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

    def test_agent_preserves_reasoning_metadata_across_tool_round(self, session):
        tool_name = f"reasoning_probe_{uuid4().hex}"

        @tool(name=tool_name, description="Probe")
        def reasoning_probe() -> str:
            return "tool result"

        provider = Mock()
        provider.chat.side_effect = [
            Response(
                content="",
                reasoning_content="模型推理",
                reasoning_blocks=[{"type": "thinking", "thinking": "内部推理", "signature": "sig-1"}],
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": tool_name, "arguments": "{}"},
                    }
                ],
                finish_reason="tool_calls",
            ),
            Response(content="done", tool_calls=None, finish_reason="stop"),
        ]
        agent = AgentCore(provider, session)

        assert agent.chat("run") == "done"

        assistant_tool_messages = [
            msg for msg in session.messages
            if msg["role"] == "assistant" and msg.get("tool_calls")
        ]
        assert assistant_tool_messages[0]["reasoning_content"] == "模型推理"
        assert assistant_tool_messages[0]["reasoning_blocks"] == [
            {"type": "thinking", "thinking": "内部推理", "signature": "sig-1"}
        ]

    def test_agent_tool_and_thinking_events_include_agent_name(self, session):
        tool_name = f"agent_event_probe_{uuid4().hex}"

        @tool(name=tool_name, description="Probe")
        def agent_event_probe() -> str:
            return "tool result"

        provider = Mock()
        provider.chat.side_effect = [
            Response(
                content="我需要先调用工具查看信息。" + "甲" * 200,
                tool_calls=[
                    {
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": tool_name, "arguments": "{}"},
                    }
                ],
                finish_reason="tool_calls",
            ),
            Response(content="done", tool_calls=None, finish_reason="stop"),
        ]
        agent = AgentCore(provider, session, tool_context={"agent_name": "writer"})
        thinking_events = []
        tool_called_events = []
        tool_result_events = []
        agent.event_bus.subscribe(EventType.THINKING, thinking_events.append)
        agent.event_bus.subscribe(EventType.TOOL_CALLED, tool_called_events.append)
        agent.event_bus.subscribe(EventType.TOOL_RESULT, tool_result_events.append)

        assert agent.chat("run") == "done"

        assert thinking_events[0].data["agent_name"] == "writer"
        assert tool_called_events[0].data["agent_name"] == "writer"
        assert tool_result_events[0].data["agent_name"] == "writer"
