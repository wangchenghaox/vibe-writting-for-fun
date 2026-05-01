import os
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import WebSocketDisconnect

from app.agent.core import AgentCore
from app.agent.session import Session
from app.capability.tool_registry import get_tool_schemas, tool
from app.core.security import create_access_token
from app.events.event_types import Event, EventType
from app.models.novel import Novel
from app.models.user import User


def test_web_agent_import_registers_all_novel_tools():
    import app.services.web_agent  # noqa: F401

    tool_names = {schema["function"]["name"] for schema in get_tool_schemas()}

    assert {
        "create_novel",
        "save_chapter",
        "load_chapter",
        "save_outline",
        "load_outline",
        "review_chapter",
        "web_search",
        "remember_memory",
        "search_memory",
        "list_memories",
        "archive_memory",
    }.issubset(tool_names)


def test_web_agent_does_not_mutate_current_novel_env(monkeypatch):
    import app.services.web_agent as web_agent

    monkeypatch.setenv("CURRENT_NOVEL_ID", "original")
    monkeypatch.setattr(web_agent, "create_provider", lambda: Mock())

    web_agent.WebAgentService("web-novel")

    assert os.environ["CURRENT_NOVEL_ID"] == "original"


def test_web_agent_uses_unique_session_per_connection(monkeypatch):
    import app.services.web_agent as web_agent

    monkeypatch.setattr(web_agent, "create_provider", lambda: Mock())

    first = web_agent.WebAgentService("shared-novel")
    second = web_agent.WebAgentService("shared-novel")

    try:
        assert first.session.id != second.session.id
        assert first.session.context["novel_id"] == "shared-novel"
        assert second.session.context["novel_id"] == "shared-novel"
        assert first.agent.tool_context["novel_id"] == "shared-novel"
        assert second.agent.tool_context["novel_id"] == "shared-novel"
    finally:
        first.close()
        second.close()


def test_web_agent_chat_forwards_streaming_deltas(monkeypatch):
    import app.services.web_agent as web_agent

    class FakeProvider:
        def chat_stream_response(self, messages, tools=None):
            yield SimpleNamespace(type="content_delta", content="你")
            yield SimpleNamespace(type="content_delta", content="好")
            yield SimpleNamespace(
                type="message_end",
                response=SimpleNamespace(content="你好", tool_calls=None),
            )

    events = []
    monkeypatch.setattr(web_agent, "create_provider", lambda: FakeProvider())

    service = web_agent.WebAgentService("stream-novel", on_event=events.append)
    try:
        assert service.chat("hello") == "你好"
    finally:
        service.close()

    assert [
        event.data["content"] for event in events
        if getattr(event.type, "value", None) == "message_delta"
    ] == ["你", "好"]


def test_agent_injects_context_novel_id_when_tool_call_omits_it():
    tool_name = f"context_probe_{uuid4().hex}"

    @tool(name=tool_name, description="Return the injected novel id")
    def context_probe(novel_id: str = None) -> str:
        return novel_id or "missing"

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

    agent = AgentCore(provider, Session("ctx-session"), tool_context={"novel_id": "novel_ctx"})

    assert agent.chat("run") == "done"
    second_call_messages = provider.chat.call_args_list[1].args[0]
    assert any(
        msg["role"] == "tool" and msg["content"] == "novel_ctx"
        for msg in second_call_messages
    )


def test_novel_api_reads_backend_data_dir(test_db):
    from app.api.novels import list_novels

    user = User(username=f"user_{uuid4().hex}", password_hash="hash")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    novel_id = f"novel_{uuid4().hex}"
    novel = Novel(user_id=user.id, novel_id=novel_id, title="测试小说", description="")
    test_db.add(novel)
    test_db.commit()

    novel_dir = Path("data/novels") / novel_id
    chapters_dir = novel_dir / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    (chapters_dir / "chapter_1.json").write_text(
        json.dumps({"id": "chapter_1", "title": "第一章", "content": "hello"}),
        encoding="utf-8",
    )

    try:
        result = list_novels(db=test_db, user=user)
    finally:
        shutil.rmtree(novel_dir, ignore_errors=True)

    row = next(item for item in result if item["novel_id"] == novel_id)
    assert row["chapter_count"] == 1
    assert row["total_words"] == 5


@pytest.mark.asyncio
async def test_websocket_event_callback_is_thread_safe(monkeypatch, test_db):
    import app.api.websocket as websocket_module

    user = User(username=f"ws_{uuid4().hex}", password_hash="hash")
    test_db.add(user)
    test_db.commit()
    test_db.refresh(user)

    novel = Novel(user_id=user.id, novel_id=f"novel_{uuid4().hex}", title="Web", description="")
    test_db.add(novel)
    test_db.commit()
    test_db.refresh(novel)

    class FakeWebSocket:
        def __init__(self):
            self.sent = []
            self.closed = False
            self._received = False

        async def accept(self):
            pass

        async def close(self, code):
            self.closed = True

        async def receive_json(self):
            if self._received:
                raise WebSocketDisconnect()
            self._received = True
            return {"type": "message", "content": "hello"}

        async def send_json(self, payload):
            self.sent.append(payload)

    class FakeAgentService:
        initialized_with = []

        def __init__(self, novel_id, on_event=None):
            self.initialized_with.append(novel_id)
            self.on_event = on_event

        def chat(self, message):
            self.on_event(
                Event(EventType.TOOL_CALLED, {"name": "save_chapter", "args": {}}, "fake")
            )
            return "ok"

        def close(self):
            pass

    fake_ws = FakeWebSocket()
    monkeypatch.setattr(websocket_module, "WebAgentService", FakeAgentService)

    await websocket_module.websocket_chat(
        fake_ws,
        novel_id=novel.id,
        token=create_access_token({"sub": user.id}),
        db=test_db,
    )

    assert FakeAgentService.initialized_with == [novel.novel_id]
    assert fake_ws.sent[0]["type"] == "tool_called"
    assert fake_ws.sent[-1] == {"type": "message_sent", "content": "ok"}
    assert all("no running event loop" not in str(msg) for msg in fake_ws.sent)
