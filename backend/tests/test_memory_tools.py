import json
from uuid import uuid4

from app.capability.tool_registry import execute_tool, get_tool_schemas
from app.db.base import Base
from app.models.novel import AgentMemory


def test_memory_tools_are_registered_with_hidden_context_params():
    import app.tools.memory_tools  # noqa: F401

    tool_names = {schema["function"]["name"]: schema for schema in get_tool_schemas()}

    assert {"remember_memory", "search_memory", "list_memories", "archive_memory"}.issubset(tool_names)
    remember_props = tool_names["remember_memory"]["function"]["parameters"]["properties"]
    assert "content" in remember_props
    assert "user_id" not in remember_props
    assert "novel_id" not in remember_props
    assert "agent_name" not in remember_props
    assert "agent_instance_id" not in remember_props


def test_remember_and_search_memory_tools_use_injected_namespace(monkeypatch, test_db):
    import app.tools.memory_tools as memory_tools
    from sqlalchemy.orm import sessionmaker

    TestSessionLocal = sessionmaker(bind=test_db.get_bind())
    Base.metadata.create_all(test_db.get_bind())
    monkeypatch.setattr(memory_tools, "SessionLocal", TestSessionLocal)
    novel_id = f"novel_{uuid4().hex}"

    remember_payload = json.loads(execute_tool(
        "remember_memory",
        {
            "content": "女主不能使用火系能力",
            "memory_type": "canon",
            "tags": "女主, canon",
            "importance": 5,
            "scope": "novel",
            "user_id": 999,
        },
        context={
            "user_id": 1,
            "novel_id": novel_id,
            "agent_name": "writer",
            "agent_instance_id": "instance_1",
        },
    ))

    assert remember_payload["ok"] is True
    assert remember_payload["memory"]["user_id"] == 1
    assert remember_payload["memory"]["novel_id"] == novel_id

    search_payload = json.loads(execute_tool(
        "search_memory",
        {"query": "火系", "memory_type": "canon", "tags": "女主"},
        context={
            "user_id": 1,
            "novel_id": novel_id,
            "agent_name": "reviewer",
            "agent_instance_id": "instance_2",
        },
    ))

    assert search_payload["ok"] is True
    assert search_payload["result"]["count"] == 1
    assert search_payload["result"]["items"][0]["content"] == "女主不能使用火系能力"


def test_archive_memory_tool_respects_visibility(monkeypatch, test_db):
    import app.tools.memory_tools as memory_tools
    from sqlalchemy.orm import sessionmaker

    TestSessionLocal = sessionmaker(bind=test_db.get_bind())
    Base.metadata.create_all(test_db.get_bind())
    monkeypatch.setattr(memory_tools, "SessionLocal", TestSessionLocal)
    novel_id = f"novel_{uuid4().hex}"

    memory = AgentMemory(
        user_id=2,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="note",
        content="只能 writer 归档",
        tags_json="[]",
        importance=3,
        status="active",
    )
    test_db.add(memory)
    test_db.commit()
    test_db.refresh(memory)

    reviewer_payload = json.loads(execute_tool(
        "archive_memory",
        {"memory_id": memory.id},
        context={"user_id": 2, "novel_id": novel_id, "agent_name": "reviewer"},
    ))
    writer_payload = json.loads(execute_tool(
        "archive_memory",
        {"memory_id": memory.id},
        context={"user_id": 2, "novel_id": novel_id, "agent_name": "writer"},
    ))

    assert reviewer_payload["result"]["archived"] is False
    assert writer_payload["result"]["archived"] is True
