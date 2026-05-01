import pytest
from uuid import uuid4

from app.memory.service import MemoryService


def test_create_memory_validates_required_context(test_db):
    service = MemoryService(test_db)

    with pytest.raises(ValueError, match="缺少记忆上下文"):
        service.remember(
            user_id=None,
            novel_id="novel",
            agent_name="writer",
            content="记住这个",
        )


def test_create_memory_validates_type_scope_and_importance(test_db):
    service = MemoryService(test_db)
    novel_id = f"novel_{uuid4().hex}"

    with pytest.raises(ValueError, match="不支持的 memory_type"):
        service.remember(1, novel_id, "writer", "内容", memory_type="bad")

    with pytest.raises(ValueError, match="不支持的 scope"):
        service.remember(1, novel_id, "writer", "内容", scope="global")

    memory = service.remember(
        1,
        novel_id,
        "writer",
        "内容",
        memory_type="note",
        tags="a, b，c",
        importance=99,
        scope="agent",
    )

    assert memory["importance"] == 5
    assert memory["tags"] == ["a", "b", "c"]


def test_create_memory_accepts_cli_user_id_zero(test_db):
    service = MemoryService(test_db)
    novel_id = f"novel_{uuid4().hex}"

    memory = service.remember(
        0,
        novel_id,
        "main",
        "CLI 本地记忆",
        memory_type="note",
    )

    assert memory["user_id"] == 0
    assert memory["novel_id"] == novel_id


def test_search_formats_visible_memories(test_db):
    service = MemoryService(test_db)
    novel_id = f"novel_{uuid4().hex}"

    service.remember(
        1,
        novel_id,
        "writer",
        "女主不能使用火系能力",
        memory_type="canon",
        tags="女主, canon",
        importance=5,
        scope="novel",
    )

    result = service.search(
        1,
        novel_id,
        "reviewer",
        query="火系",
        memory_type="canon",
        tags="女主",
        limit=10,
    )

    assert result["count"] == 1
    assert result["items"][0]["content"] == "女主不能使用火系能力"
    assert result["items"][0]["scope"] == "novel"
