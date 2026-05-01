from uuid import uuid4

from app.memory.repository import MemoryRepository
from app.models.novel import AgentEventLog, AgentMemory


def test_log_event_persists_payload_json(test_db):
    repo = MemoryRepository(test_db)
    novel_id = f"novel_{uuid4().hex}"

    event = repo.log_event(
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
        agent_instance_id="subagent_writer_1",
        session_id="session_1",
        event_type="user_message",
        payload={"content": "你好"},
    )

    row = test_db.query(AgentEventLog).filter(AgentEventLog.id == event.id).one()
    assert row.user_id == 1
    assert row.novel_id == novel_id
    assert row.agent_name == "writer"
    assert row.agent_instance_id == "subagent_writer_1"
    assert row.payload == {"content": "你好"}


def test_query_memories_respects_agent_private_and_novel_shared_scope(test_db):
    repo = MemoryRepository(test_db)
    novel_id = f"novel_{uuid4().hex}"

    writer_private = repo.create_memory(
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="style",
        content="写作偏好短句",
        tags=["style"],
        importance=4,
    )
    reviewer_private = repo.create_memory(
        user_id=1,
        novel_id=novel_id,
        agent_name="reviewer",
        scope="agent",
        layer="explicit",
        memory_type="constraint",
        content="审稿优先看冲突密度",
        tags=["review"],
        importance=3,
    )
    shared = repo.create_memory(
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
        scope="novel",
        layer="explicit",
        memory_type="canon",
        content="女主不能使用火系能力",
        tags=["canon", "女主"],
        importance=5,
    )

    writer_results = repo.query_memories(user_id=1, novel_id=novel_id, agent_name="writer")
    reviewer_results = repo.query_memories(user_id=1, novel_id=novel_id, agent_name="reviewer")

    assert {item.id for item in writer_results} == {writer_private.id, shared.id}
    assert {item.id for item in reviewer_results} == {reviewer_private.id, shared.id}


def test_query_memories_filters_by_user_novel_keyword_type_tags_and_limit(test_db):
    repo = MemoryRepository(test_db)
    novel_id = f"novel_{uuid4().hex}"
    other_novel_id = f"novel_{uuid4().hex}"

    match = repo.create_memory(
        user_id=2,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="character",
        content="男主害怕深水",
        tags=["男主", "弱点"],
        importance=5,
    )
    repo.create_memory(
        user_id=2,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="character",
        content="男主喜欢甜食",
        tags=["男主"],
        importance=4,
    )
    repo.create_memory(
        user_id=3,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="character",
        content="男主害怕深水",
        tags=["男主", "弱点"],
        importance=5,
    )
    repo.create_memory(
        user_id=2,
        novel_id=other_novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="character",
        content="男主害怕深水",
        tags=["男主", "弱点"],
        importance=5,
    )

    results = repo.query_memories(
        user_id=2,
        novel_id=novel_id,
        agent_name="writer",
        query="深水",
        memory_type="character",
        tags=["弱点"],
        limit=1,
    )

    assert [item.id for item in results] == [match.id]


def test_archive_memory_only_archives_visible_memory(test_db):
    repo = MemoryRepository(test_db)
    novel_id = f"novel_{uuid4().hex}"
    other_novel_id = f"novel_{uuid4().hex}"

    visible = repo.create_memory(
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="note",
        content="可归档",
        tags=[],
        importance=3,
    )
    hidden = repo.create_memory(
        user_id=1,
        novel_id=other_novel_id,
        agent_name="writer",
        scope="agent",
        layer="explicit",
        memory_type="note",
        content="不可归档",
        tags=[],
        importance=3,
    )

    assert repo.archive_memory(
        memory_id=visible.id,
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
    ) is True
    assert repo.archive_memory(
        memory_id=hidden.id,
        user_id=1,
        novel_id=novel_id,
        agent_name="writer",
    ) is False

    assert test_db.get(AgentMemory, visible.id).status == "archived"
    assert test_db.get(AgentMemory, hidden.id).status == "active"
